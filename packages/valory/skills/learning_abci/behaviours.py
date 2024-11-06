# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2024 Valory AG
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
# ------------------------------------------------------------------------------

"""This package contains round behaviours of LearningAbciApp."""

import json
from abc import ABC
from pathlib import Path
from tempfile import mkdtemp
from typing import Dict, Generator, Optional, Set, Type, cast

from packages.valory.contracts.oracle.contract import Oracle
from packages.valory.contracts.erc20.contract import ERC20
from packages.valory.contracts.gnosis_safe.contract import (
    GnosisSafeContract,
    SafeOperation,
)
from packages.valory.contracts.multisend.contract import (
    MultiSendContract,
    MultiSendOperation,
)
from packages.valory.contracts.price_keeper.contract import PriceKeeper
from packages.valory.contracts.property_registry.contract import PropertyRegistry
from packages.valory.protocols.contract_api import ContractApiMessage
from packages.valory.protocols.ledger_api import LedgerApiMessage
from packages.valory.skills.abstract_round_abci.base import AbstractRound
from packages.valory.skills.abstract_round_abci.behaviours import (
    AbstractRoundBehaviour,
    BaseBehaviour,
)
from packages.valory.skills.abstract_round_abci.io_.store import SupportedFiletype
from packages.valory.skills.learning_abci.models import (
    ArliSpecs,
    CoingeckoSpecs,
    CoinmarketcapSpecs,
    Params,
    RentcastSpecs,
    SharedState,
)
from packages.valory.skills.learning_abci.payloads import (
    DecisionMakingPayload,
    ExerciseTxPreparationPayload,
    HouseDataPayload,
)
from packages.valory.skills.learning_abci.rounds import (
    DecisionMakingRound,
    Event,
    ExerciseTxPreparationRound,
    LearningAbciApp,
    PullRealEstateRound,
    SynchronizedData,
)
from packages.valory.skills.transaction_settlement_abci.payload_tools import (
    hash_payload_to_hex,
)
from packages.valory.skills.transaction_settlement_abci.rounds import TX_HASH_LENGTH


# Define some constants
ZERO_VALUE = 0
HTTP_OK = 200
GNOSIS_CHAIN_ID = "gnosis"
EMPTY_CALL_DATA = b"0x"
SAFE_GAS = 0
VALUE_KEY = "value"
TO_ADDRESS_KEY = "to_address"
METADATA_FILENAME = "metadata.json"


class LearningBaseBehaviour(BaseBehaviour, ABC):  # pylint: disable=too-many-ancestors
    """Base behaviour for the learning_abci behaviours."""

    @property
    def params(self) -> Params:
        """Return the params. Configs go here"""
        return cast(Params, super().params)

    @property
    def synchronized_data(self) -> SynchronizedData:
        """Return the synchronized data. This data is common to all agents"""
        return cast(SynchronizedData, super().synchronized_data)

    @property
    def local_state(self) -> SharedState:
        """Return the local state of this particular agent."""
        return cast(SharedState, self.context.state)

    @property
    def coingecko_specs(self) -> CoingeckoSpecs:
        """Get the Coingecko api specs."""
        return self.context.coingecko_specs

    @property
    def coinmarketcap_specs(self) -> CoinmarketcapSpecs:
        """Get the Coingecko api specs."""
        
        return self.context.coinmarketcap_specs
    
    @property
    def arli_specs(self) -> ArliSpecs:
        """Get the Coingecko api specs."""
        
        return self.context.arli_specs
    
    @property
    def rentcast_specs(self) -> RentcastSpecs:
        """Get the Coingecko api specs."""
        
        return self.context.rentcast_specs

    @property
    def metadata_filepath(self) -> str:
        """Get the temporary filepath to the metadata."""
        return str(Path(mkdtemp()) / METADATA_FILENAME)

    def get_sync_timestamp(self) -> float:
        """Get the synchronized time from Tendermint's last block."""
        now = cast(
            SharedState, self.context.state
        ).round_sequence.last_round_transition_timestamp.timestamp()

        return now


class PullRealEstateData(LearningBaseBehaviour):  # pylint: disable=too-many-ancestors
    """This behaviours pulls property data from API endpoints and writes it to IPFS."""

    matching_round: Type[AbstractRound] = PullRealEstateRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            sender = self.context.agent_address

            house_data = yield from self.get_house_data()
            print("OUR HOUSE_DATA!!!: ", house_data)
            house_data_string = json.dumps(house_data)

            house_data_ipfs_hash = yield from self.send_house_data_to_ipfs(house_data)
        
            payload = HouseDataPayload(
                sender=sender,
                value_ipfs_hash=house_data_ipfs_hash,
                house_data=house_data_string
            )

        # Send the payload to all agents and mark the behaviour as done
        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()
    
    def get_house_data(self) -> Generator[None, None, Optional[dict]]:
        """Get house data from RentCast using ApiSpecs"""
        
        # Get the specs
        specs = self.rentcast_specs.get_spec()
    
        # Make the call
        raw_response = yield from self.get_http_response(**specs)

        # Process the response
        response = self.rentcast_specs.process_response(raw_response)

        if response and isinstance(response, list) and len(response) > 0:
            # Extract the first item from the response list
            property_data = response[0]
            
            # Extract relevant information
            extracted_data = {
                "id": property_data.get("id"),
                "formattedAddress": property_data.get("formattedAddress"),
                "price": property_data.get("lastSalePrice")  # Adjust this if needed
            }
            self.context.logger.info(f"Extracted data: {extracted_data}")
            return extracted_data
        else:
            self.context.logger.error("Failed to retrieve or process property data.")
            return None
    
    def send_house_data_to_ipfs(self, value) -> Generator[None, None, Optional[str]]:
        """Store the house data in IPFS"""
        data = value
        value_ipfs_hash = yield from self.send_to_ipfs(
            filename=self.metadata_filepath, obj=data, filetype=SupportedFiletype.JSON
        )
        self.context.logger.info(
            f"House data stored in IPFS: https://gateway.autonolas.tech/ipfs/{value_ipfs_hash}"
        )
        return value_ipfs_hash

class DecisionMakingBehaviour(
    LearningBaseBehaviour
):  # pylint: disable=too-many-ancestors
    """DecisionMakingBehaviour"""

    matching_round: Type[AbstractRound] = DecisionMakingRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            sender = self.context.agent_address

            # Make a decision: either transact or not
            event = yield from self.get_next_event()

            payload = DecisionMakingPayload(sender=sender, event=event)

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def get_next_event(self) -> Generator[None, None, str]:
        """Get the next event: decide whether ot transact or not based on some data."""

        house_data = yield from self.get_value_from_ipfs()
        if not house_data:
            self.context.logger.error("Failed to retrieve house data from IPFS.")
            return Event.DONE.value
        
        self.context.logger.info(f"HOUSE DATA FROM IPFS: {house_data}")
        
        # Prepare the modified prompt
        house_description = (
            f"Property located at {house_data.get('formattedAddress')} with an "
            f"asking price of ${house_data.get('price')}, "
            # f"built in {house_data.get('yearBuilt')}, "
            # f"and featuring {house_data.get('bedrooms')} bedrooms and {house_data.get('bathrooms')} bathrooms."
        )
        prompt = f"{house_description}\nWill this house's price increase in 5 years? Give extreme short answer. Respond with 'Yes' or 'No'."


        # Send the prompt to the LLM and get the opinion
        opinion = yield from self.get_house_price_opinion(prompt)

        # Check the response from the LLM
        if opinion:
            first_100_words = ' '.join(opinion.lower().split()[:100]) 
            if 'yes' in first_100_words:
                self.context.logger.info("LLM response indicates a positive outcome. Transacting.")
                return Event.TRANSACT.value
            else:
                self.context.logger.info("LLM response indicates a negative or uncertain outcome. Not transacting.")
                return Event.DONE.value

    def get_house_price_opinion(self, prompt: str) -> Generator[None, None, Optional[str]]:
        """Get house price opinion from Arli AI using ApiSpecs."""
        
        # Get the specs
        specs = self.arli_specs.get_spec()
        specs['parameters']['prompt'] = prompt

        self.context.logger.info(f"API Specs being used: {specs}")
        self.context.logger.info(f"Payload being sent: {json.dumps(specs['parameters'], indent=2)}")


        # Prepare the payload as JSON content
        content = json.dumps(specs['parameters']).encode('utf-8')

        # Log the content to ensure it's correctly set
        self.context.logger.info(f"Payload being sent as content: {content.decode('utf-8')}")

        # Make the API call with content as the body
        raw_response = yield from self.get_http_response(
            method=specs['method'],
            url=specs['url'],
            content=content,
            headers=specs['headers']
        )
        self.context.logger.info(f"Raw response from Arli AI: {raw_response}")

        # Process the response
        response = self.arli_specs.process_response(raw_response)
        self.context.logger.info(f"Got Arli PROCESSED response: {response}")

        # Get the opinion text
        opinion = response[0].get("text", "").strip() if response[0] else None

        if opinion:
            self.context.logger.info(f"Received house price opinion from Arli AI: {opinion}")
        else:
            self.context.logger.error("No valid opinion received from Arli AI.")
            
        return opinion
    
    def get_value_from_ipfs(self) -> Generator[None, None, Optional[dict]]:
        """Load the HOUSE data from IPFS"""
        ipfs_hash = self.synchronized_data.value_ipfs_hash

        value = yield from self.get_from_ipfs(
            ipfs_hash=ipfs_hash, filetype=SupportedFiletype.JSON
        )
        self.context.logger.error(f"Got HOUSE DATA from IPFS: {value}")
        return value


class ExerciseTxPreparationBehaviour(
    LearningBaseBehaviour
):  # pylint: disable=too-many-ancestors
    """TxPreparationBehaviour"""

    matching_round: Type[AbstractRound] = ExerciseTxPreparationRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            sender = self.context.agent_address

            # Get the transaction hash
            tx_hash = yield from self.get_tx_hash()

            payload = ExerciseTxPreparationPayload(
                sender=sender, tx_submitter=self.auto_behaviour_id(), tx_hash=tx_hash
            )

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def get_tx_hash(self) -> Generator[None, None, Optional[str]]:
        """Get the transaction hash"""

        house_data = self.synchronized_data.house_data
        print("!!!! HOUSE DATA RETRIEVED INSIDE TX PREPARATION: ", house_data)
        print(type(house_data))

        deposit_amount = 1 # TODO make deposit amount 5 percent of the house price..
        # Multisend transaction (both native and House data storage) (Safe -> recipient)
        self.context.logger.info("Preparing a multisend transaction")
        tx_hash = yield from self.get_multisend_safe_tx_hash(1, house_data=house_data)
        return tx_hash
    
    def store_house_data(self, house_data:str) -> Generator[None, None, Optional[str]]:
        """Store the HOUSE DATA from Rentcast API"""

        self.context.logger.info("Preparing HOUSE DATA storage transaction")

        # Use the contract api to interact with the Property Registry contract
        response_msg = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_RAW_TRANSACTION,  # type: ignore
            contract_address=self.params.property_registry_address,
            contract_id=str(PropertyRegistry.contract_id),
            contract_callable="save_property",
            property_data=house_data,
            chain_id=GNOSIS_CHAIN_ID,
        )

        # Check that the response is what we expect
        if response_msg.performative != ContractApiMessage.Performative.RAW_TRANSACTION:
            self.context.logger.error(
                f"Error while retrieving the balance: {response_msg}"
            )
            return None

        data_bytes: Optional[bytes] = response_msg.raw_transaction.body.get(
            "data", None
        )

        # Ensure that the data is not None
        if data_bytes is None:
            self.context.logger.error(
                f"Error while preparing the transaction: {response_msg}"
            )
            return None

        data_hex = data_bytes.hex()
        self.context.logger.info(f"Latest DAI price storage data is {data_hex}")
        return data_hex
    

    def get_native_balance(self) -> Generator[None, None, Optional[float]]:
        """Get the native balance"""
        self.context.logger.info(
            f"Getting native balance for Safe {self.synchronized_data.safe_contract_address}"
        )

        ledger_api_response = yield from self.get_ledger_api_response(
            performative=LedgerApiMessage.Performative.GET_STATE,
            ledger_callable="get_balance",
            account=self.synchronized_data.safe_contract_address,
            chain_id=GNOSIS_CHAIN_ID,
        )

        if ledger_api_response.performative != LedgerApiMessage.Performative.STATE:
            self.context.logger.error(
                f"Error while retrieving the native balance: {ledger_api_response}"
            )
            return None

        balance = cast(int, ledger_api_response.state.body["get_balance_result"])
        balance = balance / 10**18  # from wei

        self.context.logger.error(f"Got native balance: {balance}")

        return balance
    

    def get_native_transfer_safe_tx_hash(self, amount:int) -> Generator[None, None, Optional[str]]:
        """Prepare a native safe transaction"""

        # Transaction data
        # This method is not a generator, therefore we don't use yield from
        data = self.get_native_transfer_data(amount)

        # Prepare safe transaction
        safe_tx_hash = yield from self._build_safe_tx_hash(**data)
        self.context.logger.info(f"Native transfer hash is {safe_tx_hash}")

        return safe_tx_hash

    def get_native_transfer_data(self, amount:int) -> Dict:
        """Get the native transaction data"""
        # Send 1 wei to the recipient
        data = {VALUE_KEY: amount, TO_ADDRESS_KEY: self.params.transfer_target_address}
        self.context.logger.info(f"Native transfer data is {data}")
        return data

    def get_multisend_safe_tx_hash(self, amount:int, house_data:str) -> Generator[None, None, Optional[str]]:
        """Get a multisend transaction hash"""
        # Step 1: we prepare a list of transactions
        # Step 2: we pack all the transactions in a single one using the mulstisend contract
        # Step 3: we wrap the multisend call inside a Safe call, as always

        multi_send_txs = []

        # Native transfer
        native_transfer_data = self.get_native_transfer_data(amount=amount)
        multi_send_txs.append(
            {
                "operation": MultiSendOperation.CALL,
                "to": self.params.transfer_target_address,
                "value": native_transfer_data[VALUE_KEY],
                # No data key in this transaction, since it is a native transfer
            }
        )

        # store latest price transaction
        store_house_data_hex = yield from self.store_house_data(house_data=house_data)

        if store_house_data_hex is None:
            return None

        multi_send_txs.append(
            {
                "operation": MultiSendOperation.CALL,
                "to": self.params.property_registry_address,
                "value": ZERO_VALUE,
                "data": bytes.fromhex(store_house_data_hex),
            }
        )

        # Multisend call
        contract_api_msg = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_RAW_TRANSACTION,  # type: ignore
            contract_address=self.params.multisend_address,
            contract_id=str(MultiSendContract.contract_id),
            contract_callable="get_tx_data",
            multi_send_txs=multi_send_txs,
            chain_id=GNOSIS_CHAIN_ID,
        )

        # Check for errors
        if (
            contract_api_msg.performative
            != ContractApiMessage.Performative.RAW_TRANSACTION
        ):
            self.context.logger.error(
                f"Could not get Multisend tx hash. "
                f"Expected: {ContractApiMessage.Performative.RAW_TRANSACTION.value}, "
                f"Actual: {contract_api_msg.performative.value}"
            )
            return None

        # Extract the multisend data and strip the 0x
        multisend_data = cast(str, contract_api_msg.raw_transaction.body["data"])[2:]
        self.context.logger.info(f"Multisend data is {multisend_data}")

        # Prepare the Safe transaction
        safe_tx_hash = yield from self._build_safe_tx_hash(
            to_address=self.params.multisend_address,
            value=ZERO_VALUE,  # the safe is not moving any native value into the multisend
            data=bytes.fromhex(multisend_data),
            operation=SafeOperation.DELEGATE_CALL.value,  # we are delegating the call to the multisend contract
        )
        return safe_tx_hash

    def _build_safe_tx_hash(
        self,
        to_address: str,
        value: int = ZERO_VALUE,
        data: bytes = EMPTY_CALL_DATA,
        operation: int = SafeOperation.CALL.value,
    ) -> Generator[None, None, Optional[str]]:
        """Prepares and returns the safe tx hash for a multisend tx."""

        self.context.logger.info(
            f"Preparing Safe transaction [{self.synchronized_data.safe_contract_address}]"
        )

        # Prepare the safe transaction
        response_msg = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_STATE,  # type: ignore
            contract_address=self.synchronized_data.safe_contract_address,
            contract_id=str(GnosisSafeContract.contract_id),
            contract_callable="get_raw_safe_transaction_hash",
            to_address=to_address,
            value=value,
            data=data,
            safe_tx_gas=SAFE_GAS,
            chain_id=GNOSIS_CHAIN_ID,
            operation=operation,
        )

        # Check for errors
        if response_msg.performative != ContractApiMessage.Performative.STATE:
            self.context.logger.error(
                "Couldn't get safe tx hash. Expected response performative "
                f"{ContractApiMessage.Performative.STATE.value!r}, "  # type: ignore
                f"received {response_msg.performative.value!r}: {response_msg}."
            )
            return None

        # Extract the hash and check it has the correct length
        tx_hash: Optional[str] = response_msg.state.body.get("tx_hash", None)

        if tx_hash is None or len(tx_hash) != TX_HASH_LENGTH:
            self.context.logger.error(
                "Something went wrong while trying to get the safe transaction hash. "
                f"Invalid hash {tx_hash!r} was returned."
            )
            return None

        # Transaction to hex
        tx_hash = tx_hash[2:]  # strip the 0x

        safe_tx_hash = hash_payload_to_hex(
            safe_tx_hash=tx_hash,
            ether_value=value,
            safe_tx_gas=SAFE_GAS,
            to_address=to_address,
            data=data,
            operation=operation,
        )

        self.context.logger.info(f"Safe transaction hash is {safe_tx_hash}")

        return safe_tx_hash

class LearningRoundBehaviour(AbstractRoundBehaviour):
    """LearningRoundBehaviour"""

    initial_behaviour_cls = PullRealEstateData
    abci_app_cls = LearningAbciApp  # type: ignore
    behaviours: Set[Type[BaseBehaviour]] = [  # type: ignore
        PullRealEstateData,
        DecisionMakingBehaviour,
        ExerciseTxPreparationBehaviour,
    ]
