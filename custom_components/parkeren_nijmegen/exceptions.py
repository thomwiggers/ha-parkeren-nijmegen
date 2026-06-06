class NijmegenParkingError(Exception):
    pass

class AuthError(NijmegenParkingError):
    pass

class ProviderError(NijmegenParkingError):
    pass
