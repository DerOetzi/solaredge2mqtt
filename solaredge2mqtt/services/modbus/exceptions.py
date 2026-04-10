class InvalidRegisterDataException(Exception):
    """
    Exception raised when register data cannot be decoded properly.

    This typically occurs when string registers contain invalid UTF-8 data,
    indicating a device communication issue or uninitialized register.
    """

    def __init__(
        self,
        register_id: str,
        address: int,
        raw_values: list[int],
        original_error: Exception | None,
    ) -> None:
        self.register_id = register_id
        self.address = address
        self.raw_values = raw_values
        self.original_error = original_error

        message = (
            f"Invalid data in register '{register_id}' at address "
            f"{address}: {original_error}"
        )
        super().__init__(message)
