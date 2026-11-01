"""DrishtiQ Network: community-facing module (camps, interest registration, accounts, Saathi assistant).

Isolation rule: nothing in this package may import the clinical store module, open the clinical case database, or use the screening models.
It owns network.sqlite and its own authentication.
"""
