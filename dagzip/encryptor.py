"""
DAGZip Chunk Encryption Module

This module handles the secure encryption and decryption of CDC chunks.
It utilizes AES-256-GCM for Authenticated Encryption, ensuring both 
data confidentiality and integrity (protection against bit-rot/tampering).
"""

import os
import enum
from typing import Optional

# We use the cryptography.io library as it wraps highly optimized C/OpenSSL routines
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.exceptions import InvalidTag

# -------------------------------------------------------------------------
# Encryption Configuration Constants
# -------------------------------------------------------------------------
SALT_SIZE = 16   # 16 bytes is standard for cryptographic salts
NONCE_SIZE = 12  # 12 bytes (96 bits) is the standard and most efficient nonce size for GCM


class EncryptionAlgo(enum.IntEnum):
    """
    Enum representing the encryption algorithms supported by DAGZip.
    These map exactly to the byte values defined in the format.md header.
    """
    NONE = 0x00
    AES_256_GCM = 0x01


def generate_salt() -> bytes:
    """
    Generates a cryptographically secure random salt.
    This should be called once per new archive and stored in the archive header.
    """
    return os.urandom(SALT_SIZE)


class ChunkEncryptor:
    """
    A stateful encryption wrapper.
    
    We derive the AES key from the user's password once during initialization.
    Deriving the key is intentionally slow (to thwart brute-force attacks), 
    so we must never do it on a per-chunk basis.
    """
    
    def __init__(self, password: str, salt: bytes):
        """
        Initializes the encryptor, securely deriving a 256-bit key from the password.
        
        Args:
            password: The user-provided plaintext password.
            salt: The 16-byte random salt (read from header or newly generated).
        """
        self._salt = salt
        self._derive_key(password)
        
        # Instantiate the AES-GCM cipher wrapper.
        # This object is thread-safe and will be reused for all chunks.
        self._aesgcm = AESGCM(self._key)

    def _derive_key(self, password: str) -> None:
        """
        Derives a robust 32-byte (256-bit) AES key using the Scrypt Key Derivation Function.
        
        Why Scrypt? It is a memory-hard function. If an attacker tries to brute-force
        the password using a GPU cluster, Scrypt severely bottlenecks them by requiring 
        massive amounts of RAM per attempt, making GPU cracking economically unfeasible.
        """
        # Note: These parameters (n=2**14, r=8, p=1) are standard recommendations
        # for a good balance between fast local use and strong brute-force resistance.
        kdf = Scrypt(
            salt=self._salt,
            length=32,  # 32 bytes = 256 bits for AES-256
            n=2**14,    # CPU/Memory cost parameter
            r=8,        # Block size parameter
            p=1,        # Parallelization parameter
        )
        # Convert string password to bytes and derive the key
        self._key = kdf.derive(password.encode('utf-8'))

    def encrypt(self, data: bytes, algo: EncryptionAlgo = EncryptionAlgo.AES_256_GCM) -> bytes:
        """
        Encrypts a chunk of data (which is usually already compressed).
        
        Args:
            data: The raw or compressed binary data.
            algo: The encryption algorithm to use.
            
        Returns:
            The securely encrypted payload, prepended with its unique nonce.
        """
        if algo == EncryptionAlgo.NONE:
            return data
            
        elif algo == EncryptionAlgo.AES_256_GCM:
            # 1. Generate a mathematically unique 12-byte nonce for THIS chunk.
            nonce = os.urandom(NONCE_SIZE)
            
            # 2. Encrypt the data.
            # The encrypt() method automatically computes the 16-byte authentication tag
            # and appends it to the end of the ciphertext.
            ciphertext = self._aesgcm.encrypt(nonce, data, associated_data=None)
            
            # 3. Prepend the nonce so the decryptor knows what nonce to use later.
            # Final output structure: [12-byte Nonce] + [Ciphertext] + [16-byte Tag]
            return nonce + ciphertext
            
        else:
            raise ValueError(f"Unknown encryption algorithm: {algo}")

    def decrypt(self, encrypted_payload: bytes, algo: EncryptionAlgo) -> bytes:
        """
        Decrypts an encrypted chunk payload.
        
        Args:
            encrypted_payload: The binary blob read from the chunk pool.
            algo: The algorithm used (read from header).
            
        Raises:
            ValueError: If the payload is too short or corrupted.
            InvalidTag: If the data was tampered with or the wrong password was used.
            
        Returns:
            The decrypted, original binary data.
        """
        if algo == EncryptionAlgo.NONE:
            return data
            
        elif algo == EncryptionAlgo.AES_256_GCM:
            # 1. Ensure the payload is at least as large as the Nonce + Tag overhead
            if len(encrypted_payload) < NONCE_SIZE + 16:
                raise ValueError("Encrypted payload is too small to contain nonce and tag.")
                
            # 2. Extract the nonce from the front of the payload
            nonce = encrypted_payload[:NONCE_SIZE]
            ciphertext_with_tag = encrypted_payload[NONCE_SIZE:]
            
            try:
                # 3. Decrypt and authenticate.
                # If the data or tag was altered by even a single bit, this will raise InvalidTag.
                return self._aesgcm.decrypt(nonce, ciphertext_with_tag, associated_data=None)
            except InvalidTag:
                raise ValueError("Data corruption detected or incorrect password provided!")
                
        else:
            raise ValueError(f"Unknown decryption algorithm: {algo}")

if __name__ == "__main__":
    # Execution guard to verify cryptographic operations
    print("DAGZip Encryptor Module")
    
    test_password = "super_secure_password_123!"
    test_salt = generate_salt()
    
    encryptor = ChunkEncryptor(password=test_password, salt=test_salt)
    
    # Simulate a compressed chunk of data
    original_chunk = b"This is a secret, highly compressed chunk of data from dagzip."
    print(f"Original: {original_chunk}")
    
    # Encrypt
    encrypted = encryptor.encrypt(original_chunk)
    print(f"\nEncrypted (Nonce + Ciphertext + Tag): \n{encrypted.hex()}")
    
    # Decrypt
    decrypted = encryptor.decrypt(encrypted, EncryptionAlgo.AES_256_GCM)
    print(f"\nDecrypted: {decrypted}")
    
    assert original_chunk == decrypted
    print("\nEncryption/Decryption verified successfully.")
