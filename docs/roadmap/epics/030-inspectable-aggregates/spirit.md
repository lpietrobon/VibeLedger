# The spirit of this epic

When VibeLedger shows an interesting number, category, chart point, or flow, the
user should be able to reach the exact transactions that explain it. The product
should not make someone reconstruct dates, categories, or accounting rules by hand
just to understand what they are seeing.

The interaction has two durable parts: establish an exact scope, then inspect or
act on that set. The rows reached from an aggregate must use the same meaning of
spending, categories, dates, transfers, and refunds as the aggregate itself. If the
two disagree, navigation is not useful—it weakens trust.

This remains deterministic work. Existing Activity filters should do the job when
they are sufficient, and shared behavior should stay small until repeated use
proves that a broader abstraction is warranted. The goal is not yet a general
assistant or an open-ended analysis system.

Success means the user can investigate the important aggregate views directly and
confidently, while VibeLedger gains a grounded evidence path that future
intelligence can build on rather than replace.
