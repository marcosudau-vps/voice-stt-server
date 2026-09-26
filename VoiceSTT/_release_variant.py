"""Baked V1 product-variant identity.

Source/development checkouts default to the Community/Free runtime. The V1
product-wheel assembler rewrites this module inside each final wheel so a Pro
installation identifies itself without any environment variable or credential.
"""

KROKO_VARIANT = "free"
