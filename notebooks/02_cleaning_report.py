import marimo

app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    mo.md(
        """
        # Phase 3 — Cleaning and Feature Decisions

        **Status: see the approval status below.**

        This notebook profiles the mature 2019–2025 block-year population,
        audits target leakage, and surfaces the feature and management lever
        lists.
        """
    )
    return


@app.cell
def _():
    from pathlib import Path

    from omp_yield.cleaning import (
        DROP_COLUMNS,
        ID_COLUMNS,
        _apply_approved_decisions,
        _approved_features,
        _approved_levers,
        build_population,
        by_year_summary,
        consistency_checks,
        domain_checks,
        feature_decisions,
        latest_snapshot,
        leakage_checks,
        load_snapshot,
        management_levers,
        missingness_table,
        numeric_signal,
        outlier_table,
        redundancy_pairs,
        target_summary,
        vif_table,
    )

    snapshot_dir = latest_snapshot(Path("data/raw"))
    snapshot = load_snapshot(snapshot_dir, verify=True)
    population = build_population(snapshot.tables["OILPALM"])
    mature = population["mature"]
    missing = missingness_table(mature)
    targets = target_summary(population)
    yearly = by_year_summary(mature)
    outliers = outlier_table(mature, missing)
    domains = domain_checks(mature)
    consistency = consistency_checks(mature, snapshot.tables)
    leakage = leakage_checks(population["usable"])
    exclude = set(ID_COLUMNS) | set(DROP_COLUMNS) | {
        column
        for column in snapshot.tables["OILPALM"].columns
        if column.startswith("Y_")
    }
    signal = numeric_signal(mature, exclude)
    vif = vif_table(mature, signal)
    redundancy = redundancy_pairs(mature, signal)
    approved_features = _approved_features(Path("config"))
    approved_levers = _approved_levers(Path("config"))
    phase_status = (
        "approved"
        if approved_features and approved_levers
        else "draft — awaiting approval"
    )
    decisions = _apply_approved_decisions(
        feature_decisions(snapshot.tables["OILPALM"], missing, signal, vif),
        approved_features,
    )
    levers = approved_levers or management_levers(mature, snapshot.tables)
    return (
        consistency,
        decisions,
        domains,
        leakage,
        levers,
        mature,
        missing,
        outliers,
        phase_status,
        population,
        redundancy,
        signal,
        snapshot,
        targets,
        vif,
        yearly,
    )


@app.cell
def _(mo, phase_status):
    mo.md(f"**Status: {phase_status}**")
    return


@app.cell
def _(mo, snapshot, population):
    mo.md(
        f"""
        **Snapshot:** `{snapshot.path}`  
        **Verified:** `{snapshot.verification["all_ok"]}`  
        **Usable rows:** {population["usable"].height:,}  
        **Mature rows:** {population["mature"].height:,}  
        **Mature positive-target rows:** {population["mature_positive"].height:,}  
        **Anomaly rows:** {population["anomalies"].height:,}
        """
    )
    return


@app.cell
def _(mo, population):
    mo.md("## Flagged anomalies")
    mo.ui.table(population["anomalies"], selection=None)
    return


@app.cell
def _(mo, targets, yearly):
    mo.md("## Target distribution")
    mo.ui.table(targets, selection=None)
    mo.md("### Target by year")
    mo.ui.table(yearly, selection=None)
    return


@app.cell
def _(mo, missing):
    mo.md("## Missingness — top 30 mature columns")
    mo.ui.table(
        missing.sort("missing_pct", descending=True).head(30),
        selection=None,
    )
    return


@app.cell
def _(mo, leakage):
    mo.md(
        """
        ## Leakage checks

        Current-year `Y_*` fields are excluded. The checks below verify known
        identities such as `Y_TH = Y_TOTAL_ton / area_ha`.
        """
    )
    mo.ui.table(leakage, selection=None)
    return


@app.cell
def _(mo, domains):
    mo.md("## Domain checks")
    mo.ui.table(domains, selection=None)
    return


@app.cell
def _(mo, outliers):
    mo.md("## Outliers — top 30 numeric columns")
    mo.ui.table(outliers.head(30), selection=None)
    return


@app.cell
def _(mo, consistency):
    mo.md("## Consistency checks")
    mo.ui.table(consistency, selection=None)
    return


@app.cell
def _(mo, signal):
    mo.md("## Numeric association with target")
    mo.ui.table(signal.head(40), selection=None)
    return


@app.cell
def _(mo, vif, redundancy):
    mo.md("## Multicollinearity")
    mo.md("High-VIF features:")
    mo.ui.table(vif.head(30), selection=None)
    mo.md("High-correlation pairs (`|r| >= 0.95`):")
    mo.ui.table(redundancy.head(30), selection=None)
    return


@app.cell
def _(mo, decisions):
    mo.md("## Draft feature decisions")
    mo.ui.table(
        decisions.select(
            [
                "source",
                "name",
                "decision",
                "role",
                "available_at",
                "adjustable",
                "missing_pct",
                "pearson_r",
                "vif",
                "reason",
            ]
        ),
        selection=None,
    )
    return


@app.cell
def _(decisions, mo):
    derived = decisions.filter(decisions["derived"]).select(
        ["name", "source", "derived_from", "derivation", "decision"]
    )
    mo.md(
        """
        ## Derived feature provenance

        These are not raw database columns. They must be implemented and tested
        in Phase 4.
        """
    )
    mo.ui.table(derived, selection=None)
    return


@app.cell
def _(mo, levers):
    import polars as pl

    mo.md("## Draft management levers")
    lever_rows = pl.DataFrame(
        [
            {
                "lever": key,
                "decision": value.get("decision"),
                "available_at": value.get("available_at"),
                "reason": value.get("reason", ""),
            }
            for key, value in levers["levers"].items()
        ]
    )
    mo.ui.table(lever_rows, selection=None)
    return


@app.cell
def _(mo):
    mo.md(
        """
        ## Artifacts and approval

        - `config/features.yaml` — draft feature decisions
        - `config/management_levers.yaml` — draft management levers
        - `data/phase-3-cleaning/feature_decisions.csv`
        - `data/phase-3-cleaning/leakage_checks.csv`
        - `data/phase-3-cleaning/missingness_mature.csv`
        - `data/phase-3-cleaning/outliers.csv`
        - `data/interim/phase-3/oilpalm_mature.parquet`
        - `data/interim/phase-3/oilpalm_anomalies.parquet`
        - `docs/phase-3-cleaning/cleaning_report.md`
        - `reports/03_cleaning_report.html`

        Resolve every `review` decision before Phase 4.
        """
    )
    return


if __name__ == "__main__":
    app.run()
