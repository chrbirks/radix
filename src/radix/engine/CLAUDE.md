# radix.engine gotchas

- mypy is strict on `engine/`; mpmath has no stubs, so `Number: TypeAlias =
  int | Mpf` with `Mpf: TypeAlias = Any` in `values.py`.
