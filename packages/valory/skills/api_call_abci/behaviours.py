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

from packages.valory.protocols.contract_api import ContractApiMessage
from packages.valory.protocols.ledger_api import LedgerApiMessage
from packages.valory.skills.abstract_round_abci.base import AbstractRound
from packages.valory.skills.abstract_round_abci.behaviours import (
    AbstractRoundBehaviour,
    BaseBehaviour,
)
from packages.valory.skills.abstract_round_abci.io_.store import SupportedFiletype
from packages.valory.skills.api_call_abci.models import (
    CoinmarketcapSpecs,
    Params,
    SharedState,
)
from packages.valory.skills.api_call_abci.payloads import (
    ApiCallPayload,
    ApiCallPayload,
)
from packages.valory.skills.api_call_abci.rounds import (
    ApiCallAbciApp,
    ApiCallRound,
    SynchronizedData,
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


class ApiCallBaseBehaviour(BaseBehaviour, ABC):  # pylint: disable=too-many-ancestors
    """Base behaviour for the api_call_abci behaviours."""

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
    def coinmarketcap_specs(self) -> CoinmarketcapSpecs:
        """Get the Coingecko api specs."""
        
        return self.context.coinmarketcap_specs

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



class ApiCallBehaviour(ApiCallBaseBehaviour):  # pylint: disable=too-many-ancestors
    """This behaviours pulls token prices from API endpoints and reads the native balance of an account"""

    matching_round: Type[AbstractRound] = ApiCallRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            sender = self.context.agent_address

            # Second method to call an API: use ApiSpecs
            # This call replaces the previous price, it is just an example
            value = yield from self.get_latest_fear_greed_specs()

            print("THE GREED AND FEAR VALUE INSIDE API CALL ABCI IS: ", value)

            # Prepare the payload to be shared with other agents
            # After consensus, all the agents will have the same price, price_ipfs_hash and balance variables in their synchronized data
            payload = ApiCallPayload(
                sender=sender,
                value=value,
                #native_balance=native_balance,
                #erc20_balance=erc20_balance,
            )

        # Send the payload to all agents and mark the behaviour as done
        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def get_latest_fear_greed_specs(self) -> Generator[None, None, Optional[float]]:
        """Get token price from Coinmarketcap using ApiSpecs"""
        
        # Get the specs
        specs = self.coinmarketcap_specs.get_spec()
    
        # Make the call
        raw_response = yield from self.get_http_response(**specs)

        # Process the response
        response = self.coinmarketcap_specs.process_response(raw_response)
        self.context.logger.info(f"Got Fear and Greed PROCESSED response INSIDE API CALL ABCI  !!!!!!!!: {response}")

        # Get the value
        value = response.get("value", None)
        self.context.logger.info(f"Got Fear and Greed index from CoinMarketCap INSIDE API CALL ABCI : {value}")
        return value

    # def send_fear_greed_value_to_ipfs(self, value) -> Generator[None, None, Optional[str]]:
    #     """Store the token price in IPFS"""
    #     data = {"fear & greed value": value}
    #     value_ipfs_hash = yield from self.send_to_ipfs(
    #         filename=self.metadata_filepath, obj=data, filetype=SupportedFiletype.JSON
    #     )
    #     self.context.logger.info(
    #         f"FEAR & GREED VALUE stored in IPFS: https://gateway.autonolas.tech/ipfs/{value_ipfs_hash}"
    #     )
    #     return value_ipfs_hash


class ApiCallRoundBehaviour(AbstractRoundBehaviour):
    """LearningRoundBehaviour"""
    initial_behaviour_cls = ApiCallBehaviour
    abci_app_cls = ApiCallAbciApp  # type: ignore
    behaviours: Set[Type[BaseBehaviour]] = [  # type: ignore
        ApiCallBehaviour,
    ]
