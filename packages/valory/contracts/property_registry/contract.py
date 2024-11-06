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

"""This module contains the class to connect to the Property Registry contract."""

from typing import Dict

from aea.common import JSONLike
from aea.configurations.base import PublicId
from aea.contracts.base import Contract
from aea.crypto.base import LedgerApi
from aea_ledger_ethereum import EthereumApi


PUBLIC_ID = PublicId.from_str("valory/property_registry:0.1.0")


class PropertyRegistry(Contract):
    """The PropertyRegistry contract."""

    contract_id = PUBLIC_ID

    @classmethod
    def save_property(
        cls,
        ledger_api: EthereumApi,
        contract_address: str,
        property_data: str 
    ) -> Dict[str, bytes]:
        """Build a save property transaction."""
        
        contract_instance = cls.get_instance(ledger_api, contract_address)
        data = contract_instance.encodeABI("saveProperty", args=(property_data,))
        return {"data": bytes.fromhex(data[2:])}
    