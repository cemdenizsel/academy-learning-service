# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2023-2024 Valory AG
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

"""This module contains the class to connect to an ERC20 token contract."""

from typing import Dict

from aea.common import JSONLike
from aea.configurations.base import PublicId
from aea.contracts.base import Contract
from aea.crypto.base import LedgerApi
from aea_ledger_ethereum import EthereumApi


PUBLIC_ID = PublicId.from_str("valory/price_keeper:0.1.0")


class PriceKeeper(Contract):
    """The PriceKeeper contract."""

    contract_id = PUBLIC_ID

    @classmethod
    def get_latest_price(
        cls,
        ledger_api: EthereumApi,
        contract_address: str,
    ) -> JSONLike:
        """Check the latest price of the DAI with the timestamp."""
        contract_instance = cls.get_instance(ledger_api, contract_address)
        latest_price, timestamp = contract_instance.functions.getLatestPrice().call()
        return dict(latest_price=latest_price, timestamp=timestamp)
    
    @classmethod
    def store_latest_price(
        cls,
        ledger_api: EthereumApi,
        contract_address: str,
        latest_price: int,
        timestamp: int
    ) -> Dict[str, bytes]:
        """Build a set price transaction."""
        contract_instance = cls.get_instance(ledger_api, contract_address)
        data = contract_instance.encodeABI("setPrice", args=(latest_price, timestamp, ))
        return {"data": bytes.fromhex(data[2:])}