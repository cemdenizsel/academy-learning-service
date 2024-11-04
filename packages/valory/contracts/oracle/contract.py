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


PUBLIC_ID = PublicId.from_str("valory/oracle:0.1.0")


class Oracle(Contract):
    """The Oracle contract."""

    contract_id = PUBLIC_ID

    # @classmethod
    # def check_balance(
    #     cls,
    #     ledger_api: EthereumApi,
    #     contract_address: str,
    #     account: str,
    # ) -> JSONLike:
    #     """Check the balance of the given account."""
    #     contract_instance = cls.get_instance(ledger_api, contract_address)
    #     balance_of = getattr(contract_instance.functions, "balanceOf")  # noqa
    #     token_balance = balance_of(account).call()
    #     wallet_balance = ledger_api.api.eth.get_balance(account)
    #     return dict(token=token_balance, wallet=wallet_balance)
    
    @classmethod
    def get_latest_answer(
        cls,
        ledger_api: EthereumApi,
        contract_address: str
    ) -> JSONLike:
        """Fetch the latest answer from the Dai Oracle contract."""
        contract_instance = cls.get_instance(ledger_api, contract_address)
        latest_answer = contract_instance.functions.latestAnswer().call()
        return dict(answer=latest_answer)