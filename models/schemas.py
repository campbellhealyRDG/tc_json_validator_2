"""Data models for JSON validation."""
from enum import Enum
from typing import Optional, Dict, Any, Union, Literal
from pydantic import BaseModel, Field, SecretStr, validator, root_validator


class CustomerData(BaseModel):
    """Nested customer data schema."""
    CustomerID: str = Field(..., min_length=7)
    CustomerCardNumber: SecretStr = Field(..., min_length=16, max_length=16)
    CustomerDetails: Optional[Dict[str, Any]] = Field(default=None)
    
    class Config:
        """Pydantic configuration."""
        extra = "allow"  # Allow additional fields in CustomerData


class StructureType(str, Enum):
    """Enum for tracking structure type."""
    FLAT = "flat"
    NESTED = "nested"


class JSONSchema(BaseModel):
    """Main JSON validation schema with support for both flat and nested structures."""
    OperatorID: str = Field(..., min_length=5, pattern=r"^[a-zA-Z0-9]+$")
    
    # Either direct customer fields (flat structure) or a nested Customer object
    CustomerID: Optional[str] = Field(None, min_length=7)
    CustomerCardNumber: Optional[SecretStr] = Field(None, min_length=16, max_length=16)
    Customer: Optional[CustomerData] = None
    
    # Allow additional nested data
    Metadata: Optional[Dict[str, Any]] = Field(default=None)
    
    # Track the structure type (not part of the input data)
    structure_type: Optional[StructureType] = Field(None, exclude=True)
    
    @root_validator(pre=True)
    def check_structure(cls, values):
        """Validator to ensure either flat or proper nested structure exists."""
        # Check if we have a nested Customer object
        has_nested = 'Customer' in values and values['Customer'] is not None
        
        # Check if we have direct customer fields
        has_direct_id = 'CustomerID' in values and values['CustomerID'] is not None
        has_direct_card = 'CustomerCardNumber' in values and values['CustomerCardNumber'] is not None
        has_direct_fields = has_direct_id and has_direct_card
        
        # Either we need both direct fields, or a nested Customer object
        if not (has_direct_fields or has_nested):
            raise ValueError(
                "JSON must either have CustomerID and CustomerCardNumber fields directly, "
                "or a nested Customer object with these fields"
            )
        
        # If both structures exist, that's ambiguous
        if has_direct_fields and has_nested:
            raise ValueError(
                "Ambiguous structure: Cannot have both direct customer fields and a "
                "nested Customer object. Choose one structure."
            )
        
        # Set the structure type for later use
        values['structure_type'] = StructureType.NESTED if has_nested else StructureType.FLAT
        
        return values
    
    @validator('OperatorID')
    def validate_operator_id(cls, v):
        """Additional validation for OperatorID."""
        if not v.isalnum():
            raise ValueError("OperatorID must contain only alphanumeric characters")
        return v
    
    class Config:
        """Pydantic configuration."""
        extra = "ignore"  # Ignore additional fields at the root level
        validate_assignment = True
        
    def get_structure_type(self) -> str:
        """Return the detected structure type."""
        return self.structure_type.value if self.structure_type else "unknown"
        
    def get_customer_id(self) -> str:
        """Get the customer ID regardless of structure."""
        if self.structure_type == StructureType.NESTED:
            return self.Customer.CustomerID
        return self.CustomerID
        
    def get_card_number_masked(self) -> str:
        """Get the masked card number regardless of structure."""
        if self.structure_type == StructureType.NESTED:
            raw = self.Customer.CustomerCardNumber.get_secret_value()
        else:
            raw = self.CustomerCardNumber.get_secret_value()
            
        # Return masked version - first 4 and last 4 digits visible
        return f"{raw[:4]}{'*' * 8}{raw[-4:]}" if raw else ""