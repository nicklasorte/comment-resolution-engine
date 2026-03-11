# Templates

Binary template workbooks are intentionally not committed.

Generate output workbooks with the CLI:

```bash
python -m comment_resolution_engine.cli \
  --comments inputs/comment_matrix.xlsx \
  --report inputs/report.pdf \
  --output outputs/resolution_table.xlsx \
  --config config/column_mapping.example.yaml
```
