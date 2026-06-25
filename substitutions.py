"""
Substitutions for Sphinx
"""

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.

# When you copy this into your repo, update all values as needed.

# pylint: disable=invalid-name

#################################
### Standard Sphinx variables ###
#################################

# General information about the project.
project = "doc-builder"
copyright = "2026, UCAR"  # pylint: disable=redefined-builtin
author = ""

# The short X.Y version.
version = "doc-builder_v3.5.1"

# The full version, including alpha/beta/rc tags.
release = "doc-builder"

#####################################################
### Custom variables needed for doc-builder setup ###
#####################################################

# Version label used at the top of some pages.
version_label = "the latest development code"

#######################################################
### Custom variables optional for doc-builder setup ###
#######################################################

tex_category = "Miscellaneous"

# Used by HTML help builder
htmlhelp = {
    "basename": "docbuilderdocdoc", # Output file base name
}

# Used for LaTeX output
latex = {
    "target_name": "docbuilderdoc.tex",
    "title": "doc-builder documentation",
    "documentclass": "manual", # howto, manual, or own class
    "category": tex_category,
}

# Used for man_pages and texinfo_documents
mantex = {
    "name": "docbuilderdoc",
    "title": "docbuilderdoc Documentation",
}

# Used for texinfo_documents
tex = {
    "dirmenu_entry": "docbuilderdoc",
    "description": "One line description of project.",
    "category": tex_category,
}

###############################
### Purely custom variables ###
###############################

# When you copy this into your repo, you can keep these as examples if you want, but you can also
# just delete them.

nonparamfile_disclaimer_md = (
    "**Note:** The values here should be up-to-date with those used in {{version_label}},"
    " but there may be mistakes."
)
nonparamfile_disclaimer_rst = (
    "**Note:** The values here should be up-to-date with those used in |version_label|,"
    " but there may be mistakes."
)
