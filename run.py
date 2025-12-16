"""Manual entry point to exercise the Research_ABN_Lookup module."""

from intel_engine.modules.research_abn_lookup import (
    ResearchABNLookup as Research_ABN_Lookup,
)


def main() -> None:
    profile = {
        "identity": {"full_name": "John Smith"},
        "business": {"company_names": ["Smith Holdings"]},
    }

    module = Research_ABN_Lookup()
    result = module.execute(profile)
    print(result)


if __name__ == "__main__":
    main()
