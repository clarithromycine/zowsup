"""
Network timeout configuration for connection resilience.

When network is poor, these timeouts prevent the program from hanging.
Adjust these values based on your network conditions.
"""

# Connection establishment timeout (seconds)
# Time to establish TCP connection to WhatsApp servers
CONNECT_TIMEOUT = 30

# Read operation timeout (seconds) 
# Time to receive data from the server during normal operation
READ_TIMEOUT = 60

# Write operation timeout (seconds)
# Time to complete write buffer flush
WRITE_TIMEOUT = 30

# Protocol segment read timeout (seconds)
# Time to read individual protocol segments after header
SEGMENT_READ_TIMEOUT = 60

# Protocol segment write timeout (seconds)
# Time to write and flush protocol segments
SEGMENT_WRITE_TIMEOUT = 30

# Handshake timeout (seconds)
# Time for the initial WhatsApp handshake to complete
HANDSHAKE_TIMEOUT = 45

# Login wait timeout (seconds)
# Time to wait for login to complete after connection
LOGIN_TIMEOUT = 60

# Retry backoff settings
# Initial delay between retry attempts (seconds)
RETRY_INITIAL_DELAY = 2

# Maximum delay between retry attempts (seconds)
RETRY_MAX_DELAY = 60

# Number of retry attempts for failed connections
MAX_RETRY_ATTEMPTS = 5


def get_timeout_config():
    """Return timeout configuration as a dictionary."""
    return {
        'connect': CONNECT_TIMEOUT,
        'read': READ_TIMEOUT,
        'write': WRITE_TIMEOUT,
        'segment_read': SEGMENT_READ_TIMEOUT,
        'segment_write': SEGMENT_WRITE_TIMEOUT,
        'handshake': HANDSHAKE_TIMEOUT,
        'login': LOGIN_TIMEOUT,
        'retry_initial_delay': RETRY_INITIAL_DELAY,
        'retry_max_delay': RETRY_MAX_DELAY,
        'max_retry_attempts': MAX_RETRY_ATTEMPTS,
    }
