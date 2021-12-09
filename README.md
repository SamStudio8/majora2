<div align="center">
<p align="center">
   <img src="/images/inbound-ops-patch.png" alt="Inbound Data Operations Badge" width="250"> 
</p>
<h1 align="center">Majora</h1>
<h3 align="center">The Malleable All-seeing Journal Of Research Artifacts</h3>
</div>

Majora is a Django-based wet-and-dry information management system.
Majora comprises of the database models for storing metadata on samples, files and the processes that create and link them; a web interface for users to manage their accounts and retrieve limited metadata; and a set of APIs to add, update and retrieve metadata from the database.

Majora was initially designed for a small-scale clinical metagenomics laboratory, but in March 2020 was commandeered to act as the central metadata repository for the COVID-19 Genomics UK Consortium (COG-UK) in response to the outbreak of SARS-CoV-2.
Majora has been rapidly developed and successfully scaled through several orders of sample magnitude. For more information on how Majora (and friends) has been used to underpin the analysis of well over a million SARS-CoV-2 genomes by COG-UK, [see our article published in Genome Biology](https://genomebiology.biomedcentral.com/articles/10.1186/s13059-021-02395-y).

## What makes it useful?

Although many LIMS' exist, Majora is quite good because:

* It models data from both sides of the bench, meaning samples and downstream digital files such as reads and assemblies can be indexed together
* It considers the journey of an artifact as an adventure of different processes, meaning you can reconstruct the steps a sample has taken from a tube check-in at the lab, to an upload of data to a public database
* Majora provides a polymorphic 'Artifact' model that can be expanded into any custom models you like
* Majora can be customised with quality control thresholds and have Majora apply them using any arbitrary metrics in your dataset and keep track of the QC decision
* Majora is flexible and can store almost any metadata about any artifact through its use of polymorphic models and a generic "key-value" tag namespace
* Majora has [a command client that works](https://github.com/SamStudio8/ocarina/)
* Majora even has [a limited amount of pretty cool looking documentation](https://samstudio8.github.io/majora-docs/#introduction)

Although not used for COG, Majora has some other notable features:

* Majora pushes the idea of using a `diceware` based sample naming strategy; to reduce transcribing and picking errors
* It has support for `datamatrix` barcodes which are far superior to garbage QR codes

## How can I use it?

**You should not**. The priority right now is to maintain a single instance for COG-UK and as such Majora is made available with no support. Running Majora for your own purposes without support would be a risky endeavour but you're welcome to wing it. Over the past two years, Majora has been updated with many bits of COG-UK specific business code that will make it hard for one to take this and easily use it in a different environment. We'd suggest that academics and public health agencies [see our paper](https://genomebiology.biomedcentral.com/articles/10.1186/s13059-021-02395-y) for suggestions on what a successful model system should look like.

## License

For all intents and purposes, Majora is distributed under the MIT license (see LICENSE). However, although you are under no obligation to do so, in the spirit of Majora's use as a pandemic preparedness tool you should imagine that Majora was distributed under the [Reciprocal Public License 1.5 (RPL)](https://opensource.org/licenses/RPL-1.5) and endeavour to make your bug fixes, extensions, and meaningful and valuable derivatives (whether you have deployed Majora internally or to an outside party) freely available to the wider community by submitting pull requests back to this repository (https://github.com/SamStudio8/majora).
