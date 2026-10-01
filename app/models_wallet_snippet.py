
# Add these to app/models.py if not already present:

class WalletEntry(SQLModel, table=True):
    """Member budget income / expense line."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    kind: str = Field(max_length=20, index=True)  # income | expense
    amount: float = Field(default=0.0)
    currency: str = Field(default="NGN", max_length=8)
    # income
    payment_method: Optional[str] = Field(default=None, max_length=20)  # cash | bank
    source: Optional[str] = Field(default=None, max_length=80)  # salary, profit, ...
    # expense
    category: Optional[str] = Field(default=None, max_length=80)  # school fee, utility, ...
    note: Optional[str] = Field(default=None, max_length=500)
    entry_date: date = Field(default_factory=date.today, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
