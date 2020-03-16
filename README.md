# majora
*Malleable All-seeing Journal Of Research Artifacts*

Majora is another bloody LIMS that happens to be written in Django.
Even though it's another LIMS, there are some good ideas behind Majora, namely:

* `diceware` based sample naming strategy; to reduce transcribing and picking errors
* `datamatrix` barcoding system that will attempt to reduce the time-overhead in telling the LIMS where samples are
* Nested container model that can adaquately represent any physical storage strategy
* You could run it without the internet by deploying the django-app to a local webserver
* Natively record basic sequencing experiment information as well as track samples
* Avoids using the empirically inferior QR code in favour of the superior datamatrix
* Interfaces directly with a Zebra printer by spewing out ZPL over serial to make labels happen

Despite having an excellent contrived backronym, Majora is not ready for you to use, it's barely ready for me to use. Please do not open any issues if a large creepy moon crashes into your lab as a result of invoking Majora.
