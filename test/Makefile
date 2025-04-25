python = not-set
verbose = not-set
debug = not-set

ifneq ($(python), not-set)
PYTHON=$(python)
else
PYTHON=python
endif

# we need the python path to point one level up to access the package
# and executables
PYPATH=PYTHONPATH=..:

# common args for running tests
TEST_ARGS=-m unittest discover

ifeq ($(debug), not-set)
    ifeq ($(verbose), not-set)
        # summary only output
        TEST_ARGS+=--buffer
    else
        # show individual test summary
        TEST_ARGS+=--buffer --verbose
    endif
else
    # show detailed test output
    TEST_ARGS+=--verbose
endif


# run lint
PYLINT=pylint
PYLINT_ARGS=-j 2 --rcfile=.pylint.rc

# source files
SRC = \
	../build_docs \
	../doc_builder/*.py

TEST_DIR = .

#
# testing
#
.PHONY : utest
utest : FORCE
	$(PYPATH) $(PYTHON) $(TEST_ARGS) --pattern 'test_unit_*.py'

.PHONY : stest
stest : FORCE
	$(PYPATH) $(PYTHON) $(TEST_ARGS) --pattern 'test_sys_*.py'

.PHONY : test
test : utest stest

#
# coding standards
#
.PHONY : lint
lint : FORCE
	$(PYLINT) $(PYLINT_ARGS) $(SRC) $(TEST_DIR)/test_*.py

.PHONY : black
black : FORCE
	black --check $(SRC) $(TEST_DIR)/test_*.py

#
# utilites
#
.PHONY : clean
clean : FORCE
	-rm -rf *~ *.pyc

FORCE :

