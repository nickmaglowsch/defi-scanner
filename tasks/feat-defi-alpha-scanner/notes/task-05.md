# Task 05: Protocol Deep-Link Map

- **Decisions**: Included Morpho, Spark, and Hyperliquid in the static map even though they don't appear in current `getProtocols()` results, because the task spec lists them as "if they appear" — minimal cost to add, and `protocolLink` returns null for unknowns so no risk of bad links.
- **Deviations**: None.
- **Trade-offs**: Kept as a flat object + one function (no class, no registry pattern). Would need a backend URL field if protocols become dynamic or user-configurable.
- **Risks**: None — pure static file, no runtime side effects.
