from rest_framework_csv import renderers as r

class TSVRenderer (r.CSVRenderer):
    media_type = "text/tsv"
    format = "tsv"
    writer_opts = dict(
        delimiter='\t',
    )
