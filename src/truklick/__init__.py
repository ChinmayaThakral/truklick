"""Truklick — trusted, background-capable web automation via CDP.

The platform is the product; recipes are user content (ADR-006). The core engine
here is 100% use-case-agnostic: it launches Chromium with anti-throttle flags,
speaks raw CDP for trusted input, targets elements resiliently by the DOM, and
runs user-authored recipes. No single site's logic lives in this package.

Grounded in docs/PROVEN_FACTS.md. Do not contradict a fact there without a new proof.
"""

__version__ = "0.1.5"
