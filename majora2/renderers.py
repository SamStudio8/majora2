from rest_framework_csv import renderers as r
import csv

class TSVRenderer (r.CSVRenderer):
    media_type = "text/tsv"
    format = "tsv"
    writer_opts = dict(
        quoting=csv.QUOTE_MINIMAL,
        delimiter='\t',
    )
