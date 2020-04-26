# majora
*Malleable All-seeing Journal Of Research Artifacts*

Majora is a django-based wet-and-dry information management system.
Majora is being rapidly developed as part of the COVID-19 Genomics UK Consortium (COG-UK) response to the outbreak of SARS-CoV-2.

Although many LIMS' exist, Majora is quite good because:

* It models data for both sites of the bench, meaning both samples and digital files can be stored together
* It considers artifacts as an adventure of different processes, meaning you can reconstruct the journey a sample has taken from a tube check-in at the lab, to an upload of data to a public database
* Majora provides a polymorphic 'Artifact' model that can be expanded into any custom models you like
* Majora pushes the idea of using a `diceware` based sample naming strategy; to reduce transcribing and picking errors
* It has support for `datamatrix` barcodes which are far superior to garbage QR codes
* You can define quality control thresholds and have Majora apply them to your dataset and publish the result
* Majora is flexible and can store almost any metadata about any artifact
* Majora has [a command client that works](https://github.com/SamStudio8/ocarina/)
