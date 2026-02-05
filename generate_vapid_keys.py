#!/usr/bin/env python
"""Generate VAPID keys for Web Push Notifications"""

try:
    from py_vapid import Vapid01
    
    # Generate new VAPID keys
    vapid = Vapid01()
    vapid.generate_keys()
    
    # Save to file
    vapid.save_key('vapid_private.pem')
    vapid.save_public_key('vapid_public.pem')
    
    # Print keys for .env
    with open('vapid_public.pem', 'r') as f:
        public_key = f.read()
        
    with open('vapid_private.pem', 'r') as f:
        private_key = f.read()
    
    print("\n✅ VAPID Keys generated successfully!")
    print("\n📋 Use the PEM files for your application")
    print("-" * 60)
    print("Public Key file: vapid_public.pem")
    print("Private Key file: vapid_private.pem")
    print("-" * 60)
    print("\n📄 Keys saved to:")
    print("  - vapid_private.pem (keep this secret!)")
    print("  - vapid_public.pem")
    print("\n💡 Add to .env:")
    print("VAPID_PRIVATE_KEY_FILE=vapid_private.pem")
    print("VAPID_PUBLIC_KEY_FILE=vapid_public.pem")
    print("VAPID_CLAIMS_EMAIL=mailto:your-email@example.com")
    
except ImportError:
    print("\n⚠️  py-vapid nicht installiert!")
    print("Installiere es mit: pip install py-vapid")
    print("\nAlternativ: Keys manuell generieren mit cryptography:")
    print("-" * 60)
    
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.backends import default_backend
    
    # Generate EC key pair (NIST P-256 curve for VAPID)
    private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
    public_key = private_key.public_key()
    
    # Serialize private key to PEM (SEC1 format for EC keys)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,  # EC PRIVATE KEY format
        encryption_algorithm=serialization.NoEncryption()
    )
    
    # Serialize public key to PEM
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    # Save to files
    with open('vapid_private.pem', 'wb') as f:
        f.write(private_pem)
    
    with open('vapid_public.pem', 'wb') as f:
        f.write(public_pem)
    
    print("✅ VAPID Keys generated using cryptography!")
    print("\n📋 Files created:")
    print("  - vapid_private.pem (EC PRIVATE KEY format)")
    print("  - vapid_public.pem")
    print("\n💡 Add to .env:")
    print("VAPID_PRIVATE_KEY_FILE=vapid_private.pem")
    print("VAPID_PUBLIC_KEY_FILE=vapid_public.pem")
    print("VAPID_CLAIMS_EMAIL=mailto:your-email@example.com")
