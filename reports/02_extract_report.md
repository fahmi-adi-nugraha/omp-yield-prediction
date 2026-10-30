# Phase 2 — Raw Extraction and Snapshot

Status: **complete**

## Snapshot

| Field | Value |
|---|---|
| Snapshot ID | `20261030T000000Z` |
| Extracted at | `2026-10-30T14:16:01.152694+00:00` |
| Snapshot directory | `data/raw/20261030T000000Z` |
| Source | `omp_ds_readonly@localhost:1433/omp_as_demo` |
| Database | `omp_as_demo` |
| Login | `omp_ds_readonly` |
| Git commit | `82da984ebe0b5c873e6cbb42c2163646b52a644c` |
| Git dirty | `True` |
| Config | `config/extraction.yaml` |
| Config SHA256 | `973591e1b248a0514e17b2a451cdc92633fe83ac68d728053b4826916e734f5a` |
| Manifest SHA256 | `8614c52c58e3fb5987d888965a6f19965aac09c44b2edfea7007e777a5709843` |

## Summary

- Tables extracted: **28**
- Rows extracted: **140,004**
- Parquet bytes: **4,591,906**
- All table row counts verified against `COUNT_BIG(*)`: **yes**
- Manifest: `data/raw/20261030T000000Z/manifest.json`
- Manifest checksum: `data/raw/20261030T000000Z/manifest.sha256`

## Tables

| table | rows | columns | bytes | verified | query_sha256 | parquet_sha256 |
|---|---|---|---|---|---|---|
| OILPALM | 2909 | 207 | 812260 | True | 8c4a1a6dadc5 | e9ac4100a843 |
| tbl_BBC_bunchCounts | 8316 | 9 | 18383 | True | 4d173f20fbb9 | 63076c3d451e |
| tbl_BBC_forecastABW | 1653 | 28 | 131379 | True | 50d4314e0170 | e34eaa68fe3a |
| tbl_CB_cropBudgetMt | 2908 | 32 | 296965 | True | d21b3116444a | d6e3be0d73f8 |
| tbl_CLA_auditResults | 1762 | 18 | 16812 | True | d390314f2bbb | 960860993ccb |
| tbl_CW_weatherAndWater | 29 | 167 | 61136 | True | a7d951669469 | 9f651a6409f4 |
| tbl_FN_fertActInorg_mts | 10626 | 44 | 408045 | True | 6e837439430d | 5ecc3b66e0d9 |
| tbl_FN_fertActOrg_mts | 253 | 44 | 33028 | True | 8880675c7f0d | f337dca081ee |
| tbl_FN_fertRecInorg_mts | 10951 | 32 | 169868 | True | 99929b790566 | 6a80b604e980 |
| tbl_FN_fertRecOrg_mts | 147 | 32 | 15713 | True | f84b685f91a6 | bbaa83d55622 |
| tbl_FN_nutActRec | 2909 | 52 | 164489 | True | f907cb1bc17b | 944a6be4aab1 |
| tbl_FN_soilAnalysis | 671 | 49 | 64653 | True | dd3b80d18d3f | e350c3c493cc |
| tbl_HRR_harvests | 74986 | 30 | 1151477 | True | 1c4083c53fc2 | 8635e77a8cd1 |
| tbl_PCD_pesticideAct_dt | 2369 | 11 | 17679 | True | 4cb42e33f47a | c4c7fa3bc066 |
| tbl_PCD_pesticideRec_mts | 2211 | 32 | 82967 | True | 4d123fb703d5 | 377adf902978 |
| tbl_PD_controlAct | 812 | 18 | 12790 | True | 862a45219d96 | 92be8a2e5cde |
| tbl_PD_surveys | 8132 | 16 | 86275 | True | ff242e84ee87 | d3649007d0dd |
| tbl_SC_areas | 1130 | 8 | 12449 | True | 85ef18d198ef | 71a364e165b2 |
| tbl_SC_palmCensus | 2908 | 13 | 28276 | True | cb108b8eae55 | ce732210a051 |
| tbl_SYS_fldDefs | 727 | 45 | 48242 | True | 67626e1c3fbf | 80c6b4b46323 |
| tbl_areasPalmsBIY_blk_mts | 2909 | 220 | 929847 | True | e100ec67f1d6 | e08306555080 |
| tbl_planting | 557 | 15 | 8933 | True | 793f0adbb794 | c3cc87dfe5ba |
| tbl_suDivisions | 9 | 5 | 2429 | True | b94cd8ee1ee9 | 7f75142bff4d |
| tbl_suFields | 68 | 6 | 3938 | True | 2541036b2df1 | 20f2f83cf3b6 |
| tbl_sys_UDE_fields | 34 | 10 | 6060 | True | e750f7022a2f | c2f777af0bf2 |
| tbl_sys_growthPeriods | 5 | 7 | 3492 | True | 25ae26c66054 | 518d38de48dc |
| tbl_sys_maturityAges | 1 | 3 | 1515 | True | fe457a92c387 | 0abd1111a669 |
| tbl_sys_nutrients | 12 | 7 | 2806 | True | cbf4f7d68210 | c8b2896349c2 |

## Excluded tables

| table | reason |
|---|---|
| tbl_GIS_blocks | contains a SQL Server geometry column; not required for Phase 2 yield modeling |
| tbl_su_blocks | empty table |

## Verification

- Every Parquet file was written with the configured compression
  (`zstd`).
- Each table was read with an explicit column list; no `SELECT *`.
- `row_count_file` equals `row_count_source` for every table.
- Each Parquet file has a SHA256 checksum in `manifest.json`.
- The snapshot was written to a temporary directory and renamed into place only
  after all tables and the manifest succeeded.

## Reproduce

```bash
uv run omp-yield extract --snapshot-id 20261030T000000Z --force
```

## Notes

- `data/raw/` is gitignored. Snapshots are local immutable inputs for later
  phases.
- If `Git dirty` is `True`, the code that produced this snapshot was not
  committed. Commit the pipeline before freezing a production snapshot.
- The 2026 `OILPALM` placeholder row and all 2019–2025 rows are preserved in the
  raw snapshot. Filtering belongs in Phase 3.
- `tbl_GIS_blocks` is excluded because it contains a SQL Server `geometry`
  column; it is not needed for yield modeling.
- `tbl_su_blocks` is excluded because it is empty.
