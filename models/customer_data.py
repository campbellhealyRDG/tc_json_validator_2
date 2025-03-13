from pydantic import BaseModel, Field, SecretStr
from typing import Optional, Dict, Any

class CustomerData(BaseModel):
    CustomerID: str = Field(..., min_length=7)
    # Use SecretStr for sensitive data - adds a layer of protection for card numbers
    CustomerCardNumber: SecretStr = Field(..., min_length=16, max_length=16)
    # Optional nested fields
    CustomerDetails: Optional[Dict[str, Any]] = None