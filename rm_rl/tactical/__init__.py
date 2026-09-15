"""Tactical analytics layer for the RMUC Tactical Intelligence platform.

This package turns the raw referee SQLite dataset into the aggregate, per-team,
conditional statistics that the web dashboard consumes.  It deliberately keeps
the offline-RL core untouched and reuses `rm_rl.data` for anything that needs
the feature builder or the trained policies.
"""
