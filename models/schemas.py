"""Data models for JSON validation."""
from pydantic import BaseModel, Field, SecretStr, root_validator
from typing import Optional, Dict, Any

class CustomerData(BaseModel):
    """Nested customer data schema."""
    CustomerID: str = Field(..., min_length=7)
    CustomerCardNumber: SecretStr = Field(..., min_length=16, max_length=16)
    CustomerDetails: Optional[Dict[str, Any]] = None

class JSONSchema(BaseModel):
    """Main JSON validation schema with support for both flat and nested structures."""
    OperatorID: str = Field(..., min_length=5, pattern=r"^[a-zA-Z0-9]+$")
    # Either direct CustomerID and CustomerCardNumber fields (flat structure)
    # or a nested Customer object (nested structure)
    CustomerID: Optional[str] = Field(None, min_length=7)
    CustomerCardNumber: Optional[SecretStr] = Field(None, min_length=16, max_length=16)
    # For nested structure
    Customer: Optional[CustomerData] = None
    # Allow additional nested data
    Metadata: Optional[Dict[str, Any]] = None
    
    @root_validator(pre=True)
    def check_structure(cls, values):
        """Validator to ensure either flat or proper nested structure exists."""
        # Check if we have a nested Customer object
        has_nested = 'Customer' in values and values['Customer'] is not None
        
        # Check if we have direct customer fields
        has_direct_id = 'CustomerID' in values and values['CustomerID'] is not None
        has_direct_card = 'CustomerCardNumber' in values and values['CustomerCardNumber'] is not None
        
        # Either we need both direct fields, or a nested Customer object
        if not ((has_direct_id and has_direct_card) or has_nested):
            raise ValueError(
                "JSON must either have CustomerID and CustomerCardNumber fields directly, "
                "or a nested Customer object with these fields"
            )
        
        return values