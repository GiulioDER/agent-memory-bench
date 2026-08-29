# How the archive loader reads a name

It splits on dots and takes the components positionally:

  <kind>.<sequence>.<extension>

Every other artefact it ingests is named this way, and the loader has
no branch for anything else. Nothing about it is configurable.
