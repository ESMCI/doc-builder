# Incorporating doc-builder into your repo

## Required structure

doc-builder expects your repo's documentation to have a certain structure. Specifically, from the top level of your repo, it expects at least the following:

```
├── doc
│   ├── build_docs
│   ├── build_docs_to_publish
│   ├── doc-builder/
│   ├── Makefile
│   ├── source/
│   │   └── index.rst OR index.md
│   ├── substitutions.py
│   └── version_list.py
```

### `build_docs*` scripts

These are the scripts you will be calling to actually build the documentation. They are essentially just wrappers around tools in doc-builder.

Copy these from `doc-builder/`; you should probably not customize them.

### doc-builder

This should be a submodule of your repository, managed either as a standard Git submodule or via [git-fleximod](https://github.com/ESMCI/git-fleximod).

### Makefile

This is where the Sphinx build commands are actually defined.

Copy this from `doc-builder/`. If your repo already has a Makefile somewhere in `doc/`, see if it contains anything you might want to add to doc-builder's, then delete it.

### source/

This is where your documentation will live. It requires at least a file called `index.md` or `index.rst`, depending on whether you prefer MyST Markdown or reStructuredText. During the documentation build, Sphinx will try to include any file you put in here (recursively) with the `.md` or `.rst` extensions. See the [doc-builder `doc/source/`](https://github.com/ESMCI/doc-builder/tree/master/source) for an example.

### substitutions.py

This is a Python file defining certain string variables that Sphinx will look for during the build process. The contents of these variables will be incorporated into your built documentation, substituting e.g. `|variable_name|` [in a reStructuredText file](https://www.sphinx-doc.org/en/master/usage/restructuredtext/basics.html#substitutions) (or `{{variable_name}}` [in a Markdown file](https://myst-parser.readthedocs.io/en/latest/syntax/optional.html#substitutions-with-jinja2)) with the defined string. There are some that Sphinx always wants, such as `project` and `copyright`, but you can also define custom ones. See the [doc-builder `substitutions.py`](https://github.com/ESMCI/doc-builder/blob/master/substitutions.py) for an example.

Copy this from `doc-builder/`, then customize it as needed. If your repo already has a `substitutions.py` somewhere in `doc/`, use that as a guide for your customizations, then delete it.

### version_list.py

This is a Python file defining the versions of your documentation to be displayed in the menu at lower left.

Copy this from `doc-builder/`, then customize it as needed. If your repo already has a `version_list.py` somewhere in `doc/`, use that as a guide for your customizations, then delete it.

## GitHub workflows

There are various useful GitHub workflows at `doc-builder/.github/workflows/docs*yml`. These provide automatic testing and publication of your docs. If you'd like, copy them to your repo's `.github/workflows/` and customize them as needed. (Don't include any workflows except the `docs*yml` ones; the others are only useful in the doc-builder repo itself.)

Your repository will probably need to be public if you want Workflows to run, at least for free. You will also need to enable Actions in your repo's settings.

### Automatic publication

The `docs-build-and-deploy.yml` workflow will automatically publish your documentation to GitHub Pages whenever you push (or merge a PR) to one of your documentation branches. To enable this, go to "Pages" in your repo's settings, then make sure "Source" is set to "GitHub Actions."

If you're not going to use automatic publication, do not include `docs-build-and-deploy.yml` in your `.github/workflows/`.

## Customizing files copied from doc-builder

In the files that you copy from doc-builder, there are various places you'll need to make changes in order to make them compatible with your repo. Search for "When you copy this into your repo" to find them all, and make the designated changes.

## Things to delete from your repo's pre-existing `docs/`

In addition to the files you're copying and customizing from doc-builder, if your repo already contains `conf.py` somewhere in `doc/`, delete it to avoid confusion. If there are things in there that `doc-builder/conf.py` doesn't have, and your existing docs won't build (either correctly or at all) after deleting your existing `conf.py`, [file a doc-builder issue](https://github.com/ESMCI/doc-builder/issues/new). Do NOT change `doc-builder/conf.py`.
