# encoding: utf-8 

##lns=open(__file__).readlines()
##list(gen_tests(lns))
#def gen_tests(lns,**kw):
#    yield from doc_parts(lns)
#def gen_tests

#require installed waf:
#win32:
#  pip install -I waftools
#  wafinstall -v2.0.6
#linux: 
#  git clone https://bitbucket.org/Moo7/waftools
#  cd waftools
#  pip install -e .
#  possibly edit .local to local
#  sudo wafinstall -v2.0.6 -s --user

import sys
import os
sys.path = ['..','test/mocks','mocks'] + sys.path
import pytest
import glob
import re
from rstdoc.dcx import *

'''

rstdcx, dcx.py
``````````````

'''

import subprocess
def run(x):
    if 'win' in sys.platform:
        return subprocess.run(x,shell=True)
    else:
        return subprocess.run(x,shell=False)

_lnkname=[
("""
.. _`id`:

:idname: **key words** and some more text.
And some more text.
""".splitlines(),('id', 'idname')),
("""
.. _`id`:

:idname: 

**key words** and some more text.
""".splitlines(),('id','idname')),
("""
.. _`sy7`:

A Requirement Group
-------------------
ss""".splitlines(),('sy7','A Requirement Group')),
("""
.. _`dz3`:

.. figure:: _images/exampletikz.png
  :name:""".splitlines(),('dz3','Figure 1')),
("""
.. _`dua`:

|dua|: Table legend

.. table::
  :name:""".splitlines(),('dua','Table 1')),
("""
.. _`dta`:

|dta|: Table legend

.. list-table::
  :name:""".splitlines(),('dta','Table 1')),
("""
.. _`dyi`:

|dyi|: Listing showing struct.

.. code-block:: cpp
   :name:""".splitlines(),('dyi','Code 1')),
("""
.. _`dyi`:

|dyi|: Listing showing struct.

.. code:: cpp
   :name:""".splitlines(),('dyi','Code 1')),
("""
.. _`d9x`:

.. math:: 
   :name:
""".splitlines(),('d9x','Math 1'))
]

@pytest.mark.parametrize('lnsres',_lnkname)
def test_lnkname(lnsres):
    '''
    Test the extraction of the name for different kinds of targets::

        header, figure, list-table, table, code-block, code, math, definition (:id:) 
    '''
    lns,res = lnsres
    tgts = list(RstFile.make_tgts(lns,0,
        {".. figure":1,".. math":1,".. table":1,".. code":1}
        ))
    assert next((x.target,x.lnkname) for x in tgts)==res

def test_dcx_regex():
    assert list(rexlnks.findall('|xx| A `|lnk|` here |gos11|\n')) == ['xx', 'gos11']
    assert list(rexlnks.findall('  | |xeps1| | |xeps|  |')) == ['xeps1', 'xeps']
    assert list(rexlnks.findall('     |dd_figure|: Caption here.')) == ['dd_figure']
    assert rextgt.search('.. _`_t11`:').group(1) == '_t11'
    assert rextgt.search('  .. _`_t11`:').group(1) == '_t11'
    assert rextgt.search('#) .. _`_t11`:').group(1) == '_t11'
    assert rextgt.search('- .. _`_t11`:').group(1) == '_t11'
    assert rextgt.search('2) .. _`_t11`:').group(1) == '_t11'
    assert rextgt.search('2. .. _`_t11`:').group(1) == '_t11'
    assert rextgt.search('(a) .. _`_t11`:').group(1) == '_t11'
    assert rextgt.search('| .. _`_t11`:').group(1) == '_t11'
    assert rextgt.search('  * - .. _`_t11`:').group(1) == '_t11'
    assert rexitem.match(':t11:').group(1) == 't11'
    assert rexitem.match('**t11**:').group(1) == 't11'
    assert rexitem.match('*t11*:').group(1) == 't11'
    assert reximg.search(r'.. image:: ..\img.png').group(1) == r'..\img.png' 
    assert reximg.search(r'.. |c:\x y\im.jpg| image:: /tmp/img.png').group(1) == '/tmp/img.png'
    assert reximg.search(r'.. image:: c:\tmp\img.png').group(1) == r'c:\tmp\img.png'
    assert reximg.search(r'.. figure:: \\public\img.png').group(1) == r'\\public\img.png'
    assert rerstinclude.split('.. include:: test.rst') == ['', 'test.rst', '']
    assert rerstinclude.split('.. include:: ../test.rst') == ['', '../test.rst', '']
    assert rerstinclude.split('  .. include:: ../test.rst') == ['  ', '../test.rst', '']
    assert restplinclude.split('%include("test.rst.stpl",v="aparam")') == ['', 'test.rst.stpl', '']
    assert restplinclude.split('%include("../test.rst.stpl",v="aparam")') == ['', '../test.rst.stpl', '']
    assert restplinclude.split(' % include(  "../test.rst.stpl",v="aparam")') == [' ', '../test.rst.stpl', '']
    with pytest.raises(AttributeError):
        rextgt.search('x  .. _`_t11`:').group(1)
    with pytest.raises(AttributeError):
        rextgt.search('.. .. _`_t11`:').group(1)
    with pytest.raises(AttributeError):
        rextgt.search('%# .. _`_t11`:').group(1)
    rexsubtgt.search(' .. |t-1| image:: ').group(1) == 't-1'
    with pytest.raises(AttributeError):
        rextgt.search('%# .. |t11| xx::').group(1)
    with pytest.raises(AttributeError):
        rexitem.match(':``t11``:').group(1)
    with pytest.raises(AttributeError):
        rexitem.match('.. _xx:').group(1)
    with pytest.raises(AttributeError):
        rexitem.match('.. xx:').group(1)

@pytest.yield_fixture
def tmpworkdir(tmpdir):
    """
    Create a temporary working working directory.
    """
    cwd = os.getcwd()
    os.chdir(tmpdir.strpath)
    yield tmpdir
    os.chdir(cwd)

@pytest.yield_fixture(params=['rest','stpl'])
def rstinit(request,tmpworkdir):
    smpl='tmp_%s'%request.param
    r=run(['rstdcx','--'+request.param,smpl])
    assert r.returncode == 0
    oldd=os.getcwd()
    os.chdir(os.path.join(tmpworkdir,smpl,'src'))
    yield os.getcwd()
    os.chdir(oldd)

def test_rstincluded(rstinit):
    if 'tmp_stpl' in rstinit:
        assert list(rstincluded('ra.rest.stpl',(r'./doc',))) == [
                'ra.rest.stpl', '_links_sphinx.rst']
        assert list(rstincluded('sy.rest.stpl',(r'./doc',))) == [
                'sy.rest.stpl', '_links_sphinx.rst']
        assert list(rstincluded('sr.rest.stpl',(r'./doc',))) == [
                'sr.rest.stpl', '_links_sphinx.rst']
        assert list(rstincluded('dd.rest.stpl',(r'./doc',))) == [
                'dd.rest.stpl', 'dd_included.rst.stpl', 'dd_tables.rst', 'dd_math.tpl', 'dd_diagrams.tpl', '_links_sphinx.rst']
        assert list(rstincluded('tp.rest.stpl',(r'./doc',))) == [
                'tp.rest.stpl', '_links_sphinx.rst']
    elif 'tmp_rest' in rstinit:
        assert list(rstincluded('ra.rest',(r'./doc',))) == [
                'ra.rest', '_links_sphinx.rst']
        assert list(rstincluded('sr.rest',(r'./doc',))) == [
                'sr.rest', '_links_sphinx.rst', '_links_sphinx.rst']
        assert list(rstincluded('dd.rest',(r'./doc',))) == [
                'dd.rest', 'somefile.rst', '_links_sphinx.rst']
        assert list(rstincluded('tp.rest',(r'./doc',))) == [
                'tp.rest', '_sometst.rst', '_links_sphinx.rst']

def test_init(rstinit):
    if 'tmp_stpl' in rstinit:
        assert tree('.')=="""\
├─code
│  └─some.h
├─doc
│  ├─_images
│  ├─dd.rest.stpl
│  ├─dd_diagrams.tpl
│  ├─dd_included.rst.stpl
│  ├─dd_math.tpl
│  ├─dd_tables.rst
│  ├─egcairo.pyg
│  ├─egdot.dot.stpl
│  ├─egeps.eps
│  ├─egeps1.eps
│  ├─egother.pyg
│  ├─egplt.pyg
│  ├─egpygal.pyg
│  ├─egpyx.pyg
│  ├─egsvg.svg.stpl
│  ├─egtikz.tikz
│  ├─egtikz1.tikz
│  ├─eguml.uml
│  ├─gen
│  ├─index.rest
│  ├─model.py
│  ├─ra.rest.stpl
│  ├─sr.rest.stpl
│  ├─sy.rest.stpl
│  ├─tp.rest.stpl
│  ├─utility.rst.tpl
│  └─wscript_build
├─Makefile
├─conf.py
├─dcx.py
├─docutils.conf
├─reference.docx
├─reference.odt
├─reference.tex
├─waf
├─waf.bat
├─wafw.py
└─wscript"""
    elif 'tmp_rest' in rstinit:
        assert tree('.')=="""\
├─code
│  └─some.h
├─doc
│  ├─_images
│  ├─dd.rest
│  ├─egcairo.pyg
│  ├─egdot.dot.stpl
│  ├─egeps.eps
│  ├─egeps1.eps
│  ├─egother.pyg
│  ├─egplt.pyg
│  ├─egpygal.pyg
│  ├─egpyx.pyg
│  ├─egsvg.svg.stpl
│  ├─egtikz.tikz
│  ├─egtikz1.tikz
│  ├─eguml.uml
│  ├─gen
│  ├─index.rest
│  ├─ra.rest
│  ├─sr.rest
│  ├─tp.rest
│  └─wscript_build
├─Makefile
├─conf.py
├─dcx.py
├─docutils.conf
├─reference.docx
├─reference.odt
├─reference.tex
├─waf
├─waf.bat
├─wafw.py
└─wscript"""

def test_dcx_alone_samples(rstinit,capfd):
    r=run(['python','dcx.py','--verbose'])
    assert r.returncode == 0
    out, err = capfd.readouterr()
    if 'tmp_rest' in rstinit:
        assert list(sorted(x for x in out.splitlines() if 'png_post_processor' not in x)) == list(sorted("""\
+ egdot.dot
+ egsvg.svg
doc
+ doc/_sometst.rst
+ ../build/code/some_tst.c
    doc/tp.rest
    doc/sr.rest
    doc/ra.rest
    doc/dd.rest
    doc/index.rest
+ doc/_traceability_file.rst
+ doc/_images/_traceability_file.png
+ doc/_links_sphinx.rst
+ doc/_links_latex.rst
+ doc/_links_html.rst
+ doc/_links_pdf.rst
+ doc/_links_docx.rst
+ doc/_links_odt.rst
run (['ctags', '-R', '--sort=0', '--fields=+n', '--languages=python', '--python-kinds=-i', '-f', '-', '*'],) {'cwd': 'doc', 'stdout': -1, 'stderr': -1}
+ doc/.tags""".splitlines()))
    elif 'tmp_stpl' in rstinit:
        assert list(sorted(x for x in out.splitlines() if 'png_post_processor' not in x)) == list(sorted("""\
+ dd.rest
+ dd_included.rst
+ egdot.dot
+ egsvg.svg
+ ra.rest
+ sr.rest
+ sy.rest
+ tp.rest
doc
+ doc/_sometst.rst
+ ../build/code/some_tst.c
    doc/tp.rest.stpl
    doc/sy.rest.stpl
    doc/sr.rest.stpl
    doc/ra.rest.stpl
    doc/dd.rest.stpl
        doc/dd_included.rst.stpl
        doc/dd_tables.rst
    doc/index.rest
+ doc/_traceability_file.rst
+ doc/_images/_traceability_file.png
+ doc/_links_sphinx.rst
+ doc/_links_latex.rst
+ doc/_links_html.rst
+ doc/_links_pdf.rst
+ doc/_links_docx.rst
+ doc/_links_odt.rst
run (['ctags', '-R', '--sort=0', '--fields=+n', '--languages=python', '--python-kinds=-i', '-f', '-', '*'],) {'cwd': 'doc', 'stdout': -1, 'stderr': -1}
+ doc/.tags""".splitlines()))

@pytest.mark.parametrize('cmd_result',[
 ('rstdcx dd.rest.stpl - rest',['default-role:: math',r'<dd.html#'])
,('rstdcx dd.rest.stpl - html.',['default-role:: math',r'<dd.html#'])
,('rstdcx dd.rest.stpl - docx.',['default-role:: math',r'<dd.docx#'])
,('rstdcx dd.rest.stpl - newname.docx.',['default-role:: math',r'<newname.docx#'])
,('rstdcx dd.rest.stpl - html',["DOCTYPE html",'ref="dd.html#'])
,('rstdcx dd.rest.stpl',["DOCTYPE html",'ref="dd.html#'])
,('rstdcx sr.rest.stpl - rst_html',["DOCTYPE html",'ref="sr.html#'])
,('rstdcx dd.rest.stpl - newname.docx.',['default-role:: math',r'<newname.docx#'])
,('stpl dd.rest.stpl | rstdcx - - dd.html.',['default-role:: math',r'<dd.html#'])
,('stpl dd.rest.stpl | rstdcx - - dd.html',["DOCTYPE html",'ref="dd.html#'])
])
def test_dcx_in_out(rstinit,cmd_result):
    cmd,result = cmd_result
    os.chdir('doc')
    if not os.path.exists(cmd.split()[1]):
        if cmd.startswith('stpl'):
            return
        else:
            cmd = cmd.replace('.stpl','')
    r = subprocess.run(cmd,shell=True,stdout=subprocess.PIPE)
    assert r.returncode == 0
    out = r.stdout.decode('utf-8')
    for res in result:
        assert re.search(res,out)

@pytest.mark.parametrize('cmd_exists_not_exists',[
(['dd.rest.stpl','dd.rest'],['dd.rest'],[])
,(['dd.rest.stpl','dd.html','html'],['dd.html'],['dd.rest'])
,(['dd.rest.stpl','dd.html'],['dd.html'],['dd.rest'])
,(['sr.rest.stpl','sr.html','rst_html'],['sr.html'],['sr.rest'])
,(['dd.rest.stpl','dd.docx'],['dd.docx'],['dd.rest'])
,(['dd.rest.stpl','dd.odt','pandoc'],['dd.odt'],['dd.rest'])
,(['dd.rest.stpl','dd.odt'],['dd.odt'],['dd.rest'])
,(['sr.rest.stpl','sr.odt','rst_odt'],['sr.odt'],['sr.rest'])
,(['sr.rest.stpl','sr.odt','rst'],['sr.odt'],['sr.rest'])
,(['index.rest','../../build/index.html','sphinx_html'],['../../build/index.html'],[])
,(['egcairo.pyg'],['_images/egcairo.png'],[])
,(['egdot.dot.stpl'],['_images/egdot.png'],['egdot.dot'])
,(['egeps.eps'],['_images/egeps.png'],[])
,(['egeps1.eps'],['_images/egeps1.png'],[])
,(['egother.pyg'],['_images/egother.png'],[])
,(['egplt.pyg'],['_images/egplt.png'],[])
,(['egpygal.pyg'],['_images/egpygal.png'],[])
,(['egpyx.pyg'],['_images/egpyx.png'],[])
,(['egsvg.svg.stpl'],['_images/egsvg.png'],['egsvg.svg'])
,(['egtikz.tikz'],['_images/egtikz.png'],[])
,(['egtikz1.tikz'],['_images/egtikz1.png'],[])
,(['eguml.uml'],['_images/eguml.png'],[])
,(['eguml.uml','eguml.png'],['eguml.png'],['_images/eguml.png'])
])
def test_dcx_out_file(rstinit,cmd_exists_not_exists):
    cmd,result,notexists = cmd_exists_not_exists
    tcmd = []
    tcmd.extend(cmd)
    os.chdir('doc')
    notrest = tcmd[0].replace('.stpl','')
    if not os.path.exists(tcmd[0]):
        tcmd[0] = notrest
        if len(tcmd)>1 and tcmd[1]==notrest:
            return
        notrest = None
    ncmd = [r'rstdcx']+tcmd
    r=run(ncmd)
    assert r.returncode == 0
    assert os.path.exists(result[0])
    if notrest:
        for ne in notexists:
            assert not os.path.exists(ne)

@pytest.yield_fixture(params=['docx','pdf','html'])
def makebuild(request,rstinit):
    oldd = os.getcwd()
    r=run(['make',request.param])
    assert r.returncode == 0
    os.chdir(os.path.join('..','build'))
    yield (os.getcwd(),request.param)
    os.chdir(oldd)

tree3 = lambda x: tree(x,with_dot_files=False,max_depth=3)

def test_make_samples(makebuild):
    dir,target = makebuild
    if 'tmp_rest' in dir:
        expected_no_html="""\
├─code
│  └─some_tst.c
└─doc
   └─{0}
      ├─dd.{0}
      ├─ra.{0}
      ├─sr.{0}
      └─tp.{0}"""
        if target in ['docx','pdf']:
            expected=expected_no_html.format(target)
        elif target=='html':
            expected="""\
├─code
│  └─some_tst.c
└─doc
   ├─doctrees
   │  ├─dd.doctree
   │  ├─environment.pickle
   │  ├─index.doctree
   │  ├─ra.doctree
   │  ├─sr.doctree
   │  └─tp.doctree
   └─html
      ├─_images
      ├─_sources
      ├─_static
      ├─_traceability_file.svg
      ├─dd.html
      ├─genindex.html
      ├─index.html
      ├─objects.inv
      ├─ra.html
      ├─search.html
      ├─searchindex.js
      ├─sr.html
      └─tp.html"""
        assert tree3(makebuild[0])==expected
    elif 'tmp_stpl' in dir:
        expected_no_html="""\
├─code
│  └─some_tst.c
└─doc
   └─{0}
      ├─dd.{0}
      ├─ra.{0}
      ├─sr.{0}
      ├─sy.{0}
      └─tp.{0}"""
        if target in ['docx','pdf']:
            expected=expected_no_html.format(target)
        elif target=='html':
            expected="""\
├─code
│  └─some_tst.c
└─doc
   ├─doctrees
   │  ├─dd.doctree
   │  ├─environment.pickle
   │  ├─index.doctree
   │  ├─ra.doctree
   │  ├─sr.doctree
   │  ├─sy.doctree
   │  └─tp.doctree
   └─html
      ├─_images
      ├─_sources
      ├─_static
      ├─_traceability_file.svg
      ├─dd.html
      ├─genindex.html
      ├─index.html
      ├─objects.inv
      ├─ra.html
      ├─search.html
      ├─searchindex.js
      ├─sr.html
      ├─sy.html
      └─tp.html"""
        assert tree3(makebuild[0])==expected

waf_some = ['docx','odt','pdf','html','latex','sphinx_html','sphinx_latex','rst_html','rst_latex','rst_odt']
waf_non_sphinx = [x for x in waf_some if not x.startswith('sphinx')]
waf_sphinx = [x for x in waf_some if x.startswith('sphinx')]

@pytest.yield_fixture(params=waf_some)
def wafbuild(request,rstinit):
    r1=run(['waf','configure'])
    assert r1.returncode==0
    r2=run(['waf','--docs',request.param])
    assert r2.returncode==0
    oldd = os.getcwd()
    os.chdir(os.path.join('..','build'))
    yield (os.getcwd(),request.param)
    os.chdir(oldd)

def test_waf_samples(wafbuild):
    '''
    Run Waf on the sample project.
    Waf needs to be installed 
    
    - either in the system or 
    - added manually to the root folder of the project

    '''
    is_stpl = 'tmp_stpl' in os.getcwd()
    target=wafbuild[1]
    expected_non_sphinx="""\
├─c4che
│  ├─_cache.py
│  └─build.config.py
├─code
│  └─some_tst.c
├─doc
│  └─{0}{2}
│     ├─dd.{1}
│     ├─ra.{1}
│     ├─sr.{1}
"""+("""\
│     ├─sy.{1}
""" if is_stpl else '')+"""\
│     └─tp.{1}
└─config.log"""
    if target in waf_non_sphinx:
        try:
            _,ext = target.split('_')
        except: ext = target
        if ext.endswith('latex') or ext.endswith('html'):
            extra = '\n│     ├─_images'
            if ext.endswith('html'):
                extra += '\n│     ├─_traceability_file.svg'
        else:
            extra = ''
        expected=expected_non_sphinx.format(target,ext,extra)
    elif target=='sphinx_latex':
        expected="""\
├─c4che
│  ├─_cache.py
│  └─build.config.py
├─code
│  └─some_tst.c
├─doc
│  └─sphinx_latex
│     ├─Makefile
│     ├─_static
│     ├─_traceability_file.png
│     ├─egcairo.png
│     ├─egdot.png
│     ├─egeps.png
│     ├─egeps1.png
│     ├─egother.png
│     ├─egplt.png
│     ├─egpygal.png
│     ├─egpyx.png
│     ├─egsvg.png
│     ├─egtikz.png
│     ├─egtikz1.png
│     ├─eguml.png
│     ├─footnotehyper-sphinx.sty
│     ├─make.bat
│     ├─python.ist
│     ├─index.tex
│     ├─sphinxhighlight.sty
│     ├─sphinxhowto.cls
│     ├─sphinxmanual.cls
│     └─sphinxmulticell.sty
└─config.log"""
    elif target=='sphinx_html':
        expected="""\
├─c4che
│  ├─_cache.py
│  └─build.config.py
├─code
│  └─some_tst.c
├─doc
│  └─sphinx_html
│     ├─_images
│     ├─_sources
│     ├─_static
│     ├─_traceability_file.svg
│     ├─dd.html
│     ├─genindex.html
│     ├─index.html
│     ├─ra.html
│     ├─search.html
│     ├─searchindex.js
│     ├─sr.html
│     ├─sy.html
│     └─tp.html
└─config.log"""
    for x in tree3(wafbuild[0]).splitlines():
        if not any(e in x for e in 
        '.doctrees .sty .js .inv .xdy .cls latexmk .ist'.split()):
            assert expected.find(x.strip('└─├ '))>=0

def test_selfdoc():
    selfdoc_accoridng_doc_gen=os.path.join('doc','_dcx_api.rst')
    try:
        os.remove(selfdoc_accoridng_doc_gen)
    except: pass
    main(verbose=True)
    assert os.path.exists(selfdoc_accoridng_doc_gen)

def test_docparts_after():
    res = list(doc_parts(['/// \\brief\n',"/// afun's description\n","//\n"
        ,'void afun(\n','int x //int variable\n',')\n','\n'],
        signature='cpp',relim=r'\\brief|//$',reid=r'\s(\w\+)\('))
    assert res == ['.. code-block:: cpp\n', '', '   void afun(\n',
        '   int x //int variable\n', '   )\n', '', "afun's description\n"]


