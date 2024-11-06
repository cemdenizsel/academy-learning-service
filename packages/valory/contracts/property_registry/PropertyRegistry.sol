// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract PropertyRegistry {
    string public propertyData;  

    function saveProperty(string memory _data) public {
        require(bytes(_data).length > 0, "Data cannot be empty");
        propertyData = _data;
    }

    function getPropertyDetails() public view returns (string memory) {
        return propertyData;
    }
}
