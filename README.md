# majora
*Malleable All-seeing Journal Of Research Artifacts*

Majora is a Django-based wet-and-dry information management system.
Majora comprises of the database models for storing metadata on samples, files and the processes that create and link them; a web interface for users to manage their accounts and retrieve limited metadata; and a set of APIs to add, update and retrieve metadata from the database.

Majora is being rapidly developed and has been deployed as part of the COVID-19 Genomics UK Consortium (COG-UK) response to the outbreak of SARS-CoV-2.
For more information on how Majora is used as part of COG-UK, [see our preprint](https://www.biorxiv.org/content/10.1101/2020.10.06.328328v1).

## What makes it useful?

Although many LIMS' exist, Majora is quite good because:

* It models data for both sites of the bench, meaning both samples and digital files can be stored together
* It considers artifacts as an adventure of different processes, meaning you can reconstruct the journey a sample has taken from a tube check-in at the lab, to an upload of data to a public database
* Majora provides a polymorphic 'Artifact' model that can be expanded into any custom models you like
* You can define quality control thresholds and have Majora apply them to your dataset and publish the result
* Majora is flexible and can store almost any metadata about any artifact
* Majora has [a command client that works](https://github.com/SamStudio8/ocarina/)

Although not used for COG, Majora has some other notable features:

* Majora pushes the idea of using a `diceware` based sample naming strategy; to reduce transcribing and picking errors
* It has support for `datamatrix` barcodes which are far superior to garbage QR codes

## How can I use it?

You should not. The priority right now is to maintain a single instance for COG-UK and as such Majora is made available with no support. Running Majora for your own purposes without support would be a risky endeavour but you're welcome to wing it.

## License

For all intents and purposes, Majora is distributed under the MIT license (see LICENSE). However, although you are under no obligation to do so, in the spirit of Majora's use as a pandemic preparedness tool you should imagine that Majora was distributed under the [Reciprocal Public License 1.5 (RPL)](https://opensource.org/licenses/RPL-1.5) and endeavour to make your bug fixes, extensions, and meaningful and valuable derivatives (whether you have deployed Majora internally or to an outside party) freely available to the wider community by submitting pull requests back to this repository (https://github.com/SamStudio8/majora).
