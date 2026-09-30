"""Self-test cases, design rows. Called by `selftest.self_test`."""

from __future__ import annotations

from .core import Report, exists, read
from .design import (
    DESIGN,
    LENGTH,
    check_breakpoints,
    check_design_tokens,
    css_token_scopes,
    design_token_block,
    design_token_claims,
    read_ladder,
    read_widths,
    strip_css_comments,
    token_findings,
    token_value,
)


def run(ok) -> None:
    ok(
        token_value(LENGTH, "4px") != token_value(LENGTH, "4 px"),
        "a length keeps its unit joined — CSS does not read those as one value",
    )

    sample = "\n".join(
        [
            "NEUTRALS                 light        dark",
            "--bn-bg                  #f4f5f8      #0c0e12     the page",
            "--bn-line                ink 8%       white 8%    the hairline",
            "",
            "SPACING                  --bn-1 … --bn-3 = 4 8 12",
            "RADIUS                   --bn-r-xs 4 · -sm 6 · --bn-r 8",
            "TYPE                     --bn-fs-2xs … --bn-fs-5xl   10 11 12",
            "STAGE                    --bn-stage-bg #0c0e12 · -ink #eef0f4",
        ]
    )
    claims = design_token_claims(sample)
    ok(
        {"--bn-bg", "--bn-line", "--bn-1", "--bn-2", "--bn-3", "--bn-r-xs", "--bn-r"} <= claims.names,
        "a plain row, a numbered range and a full name in a list all yield their token",
        str(sorted(claims.names)),
    )
    ok(
        claims.prefixes == {"--bn-fs"},
        "a WORDED range locks a family, because its members are not enumerable from its ends",
        str(claims.prefixes),
    )
    ok(
        any({"--bn-r-sm"} & group for group in claims.alts),
        "a bare suffix continues the name before it",
        str(claims.alts),
    )
    ok(
        claims.hexes.get("--bn-bg") == ("#f4f5f8", "#0c0e12"),
        "a row states a light value AND a dark one, and both are kept",
        str(claims.hexes.get("--bn-bg")),
    )
    ok(
        "--bn-line" not in claims.hexes,
        "an alpha of another token states no hex, so there is nothing to compare",
        str(claims.hexes),
    )
    ok(
        claims.hexes.get("--bn-stage-ink") == ("#eef0f4", None),
        "a name/value pair mid-line is read, suffix and all",
        str(claims.hexes),
    )

    scoped = "\n".join(
        [
            ":root { --bn-bg: #f4f5f8; --bn-ink: #0f1217; --legacy: var(--bn-bg); }",
            ":root[data-theme='dark'] { --bn-bg: #0c0e12; }",
            "@media (pointer: coarse) { :root { --bn-control-h: 42px; } }",
        ]
    )
    light, dark, every = css_token_scopes(scoped)
    ok(
        light.get("--bn-bg") == "#f4f5f8" and dark.get("--bn-bg") == "#0c0e12",
        "THE TWO THEMES ARE KEPT APART — merging them let a dark hex answer for a light one",
        f"light {light.get('--bn-bg')} / dark {dark.get('--bn-bg')}",
    )
    ok(
        "--legacy" not in every,
        "a legacy alias is not locked, because the doc argues for deleting it",
        str(sorted(every)),
    )
    ok(
        "--bn-control-h" in every and "--bn-control-h" not in light,
        "a token declared only under an at-rule is named but not value-compared",
        f"every={sorted(every)} light={sorted(light)}",
    )

    agreed = design_token_claims(
        "\n".join(["--bn-bg   #f4f5f8   #0c0e12   the page", "--bn-ink  #0f1217   #eef0f4   body text"])
    )
    css_light = {"--bn-bg": "#f4f5f8", "--bn-ink": "#0f1217"}
    css_dark = {"--bn-bg": "#0c0e12", "--bn-ink": "#eef0f4"}
    names = {"--bn-bg", "--bn-ink"}
    ok(
        not token_findings(agreed, css_light, css_dark, names),
        "two files that agree produce no finding",
        str(token_findings(agreed, css_light, css_dark, names)),
    )

    drifted = token_findings(agreed, dict(css_light, **{"--bn-ink": "#0f1218"}), css_dark, names)
    ok(
        len(drifted) == 1 and "#0f1217" in drifted[0].message and "#0f1218" in drifted[0].message,
        "a changed hex is reported, naming both values",
        str(drifted),
    )
    ok(
        len(drifted) == 1 and "docs/DESIGN.md" in drifted[0].message and "app/src/tokens.css" in drifted[0].message,
        "and naming both files",
        str(drifted),
    )
    dark_drift = token_findings(agreed, css_light, dict(css_dark, **{"--bn-bg": "#0c0e13"}), names)
    ok(
        len(dark_drift) == 1 and "dark theme" in dark_drift[0].message,
        "AND A DARK VALUE DRIFTING IS ITS OWN FINDING, which the merged reader could not see",
        str(dark_drift),
    )
    ok(
        len(token_findings(agreed, css_light, css_dark, {"--bn-bg"})) == 1,
        "a locked token the stylesheet never declares is reported",
        str(token_findings(agreed, css_light, css_dark, {"--bn-bg"})),
    )
    ok(
        len(token_findings(agreed, css_light, css_dark, names | {"--bn-shadow-1"})) == 1,
        "and a stylesheet token the block never locked",
        str(token_findings(agreed, css_light, css_dark, names | {"--bn-shadow-1"})),
    )

    commented, _, _ = css_token_scopes(":root {\n  --bn-ink: #08090a; /* was --bn-ink: #fff; */\n}\n")
    ok(
        commented == {"--bn-ink": "#08090a"},
        "a declaration inside a comment is not a token",
        str(commented),
    )
    elsewhere, _, _ = css_token_scopes(".card { --bn-ink: #ffffff; }\n")
    ok(
        elsewhere == {},
        "and a custom property on some other selector is not a locked token",
        str(elsewhere),
    )

    # The extractor against the real file, because the synthetic block above is written to
    # be parseable and docs/DESIGN.md is written to be read.
    if exists(DESIGN):
        block = design_token_block(read(DESIGN))
        # Discriminated on a string only the step-6 fence carries. The obvious marker —
        # `disabled`, one of its three state names — is also the last word of the `muted`
        # row in this fence, so it failed against the correct block. Measured, not guessed.
        # The POSITIVE marker moved with the block: it read `Spacing`, which the `--bn-`
        # rewrite spells `SPACING`, and a self-test pinned to a heading's case is pinned to
        # the wrong thing. A token prefix no other fence in the file uses is the durable one.
        ok(
            block is not None and "--bn-" in block and "44px tall" not in block,
            "the Tokens fence is the one extracted, not step 6's button states",
            (block or "")[:70],
        )
    report = Report()
    check_design_tokens(report)
    by_label = {row.check: row.findings for row in report.checks}
    ok(
        not by_label["design tokens"],
        "this repo's own tokens.css agrees with docs/DESIGN.md",
        str(by_label["design tokens"]),
    )

    print("\na breakpoint reader sees rules and not the prose about them")
    _css = ("/* the 768-1023px media rail, and 640 here is wrong on purpose */\n"
            "@media (max-width: 767px) { .a { color: red } }\n"
            "@media (min-width: 768px) and (max-width: 1023px) { .b { color: red } }\n"
            "@container pane (min-width: 560px) { .c { color: red } }\n"
            ".d { container-name: pane; }\n")
    _w = read_widths(_css)
    ok(
        _w.media == [("max", 767, 2), ("min", 768, 3), ("max", 1023, 3)],
        "only the RULES' widths, with the line the rule is on",
        str(_w.media),
    )
    ok(
        not any(v == 640 for _, v, _ in _w.media),
        "AND THE DEFECT: a comment naming 768-1023px and 640 contributes no widths",
        str(_w.media),
    )
    ok(
        _w.container == [("min", 560, 4)] and _w.queried == {"pane"} and _w.declared == {"pane"},
        "a container query is its own namespace, and is read from both sides",
        f"{_w.container} {_w.queried} {_w.declared}",
    )

    print("\nthe register is read as four sections, not as one list")
    _reg = ("LADDER          the shared vocabulary\n"
            "  768           the tablet\n"
            "REFINEMENTS     one screen's own\n"
            "  1500          ReviewQueue — the rail becomes a sheet\n"
            "CONTAINER       measured against a column\n"
            "  pane    560   BoxBrowse — the band splits\n"
            "  (unnamed) 520, 640   RunPanel — the detail's own steps\n"
            "COLUMN-BLIND    the exemptions\n"
            "  Fulfillment.css   draws no shell of its own\n")
    _l = read_ladder(_reg)
    ok(_l.steps == {768: "the tablet"}, "a ladder step keeps its reason", str(_l.steps))
    ok(
        1500 in _l.refinements and 1500 not in _l.steps,
        "AND THE DEFECT: a refinement is not silently promoted to a step every sheet may use",
        str(_l.refinements),
    )
    ok(
        _l.container == {560, 520, 640},
        "a container row contributes its widths, including several on one line",
        str(_l.container),
    )
    ok(
        list(_l.blind) == ["Fulfillment.css"] and not any(
            k in _l.steps or k in _l.refinements for k in (0,)),
        "a sheet name under COLUMN-BLIND is not read as a width",
        str(_l.blind),
    )
    report = Report()
    check_breakpoints(report)
    by_label = {row.check: row.findings for row in report.checks}
    ok(
        not by_label["breakpoints"],
        "this repo's own stylesheets agree with the register",
        str(by_label["breakpoints"]),
    )

    print("\na color literal is found in CSS, and not in a comment about one")
    ok(
        strip_css_comments("a { color: #fff; } /* not #000 */").count("#") == 1,
        "a hex inside a block comment is stripped",
        strip_css_comments("a { color: #fff; } /* not #000 */"),
    )
    ok(
        strip_css_comments("/* two\nlines */\n.x{}").splitlines()[2] == ".x{}",
        "stripping preserves line numbers, so a finding points at the right line",
        str(strip_css_comments("/* two\nlines */\n.x{}").splitlines()),
    )
