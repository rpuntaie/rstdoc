#!/usr/bin/env python
#encoding: utf-8 

"""
.. _`dcx`:

rstdcx, dcx.py
==============

Support script to create documentation (PDF, HTML, DOCX)
from restructuredText (RST). 

- For HTML ``Sphinx`` is used.
- For PDF ``Pandoc`` is used (``Sphinx`` would work, too).
- For DOCX ``Pandoc`` is used, therefore *no Sphinx extension*.

``rstdcx``, or ``dcx.py`` creates

- _links_pdf.rst _links_docx.rst _links_sphinx.rst

- .tags

- processes ``gen`` files (see examples produced by --init)

See example at the end of ``dcx.py``.

Usage
-----

If installed ``./dcx.py`` can be replaced by ``rstdcx``.

Initialize example tree::

  $ ./dcx.py --init tmp

Only create .tags and _links_xxx.rst::

  $ cd tmp/src/doc
  $ ./dcx.py

Create the docs (and .tags and _links_xxx.rst)::

  $ make html
  $ make docx
  $ make pdf

Instead of using ``make`` one can load this file in `waf <https://github.com/waf-project/waf>`__.
``waf`` also considers all recursively included files, such that a change in any of them
results in a rebuild of the documentation. ``bld.stpl`` uses 
`SimpleTemplate <https://bottlepy.org/docs/dev/stpl.html#simpletemplate-syntax>`__,
which is useful, if one wants to fill in values while converting from a ``x.rst.stpl`` file.
To test this, you will need to copy ``waf`` and ``waf.bat``, created by ``python waf-light``, 
into ``src`` generated by ``--init``. Then rename e.g. ``ra.rest`` to ``ra.rest.stpl`` and do::

  $ waf configure
  $ waf --docs html,pdf,docx

Hyperlinks work in HTML, DOCX and PDF (``[Alt]+[<-]`` to go back after a jump in Acrobat Reader).

Conventions
-----------

- Main files have ``.rest`` extension, converted by Sphinx and Pandoc.
- Included files have extension ``.rst`` ignored by Sphinx (see conf.py).
- ``.. _`id`:`` are targets.
- References use replacement `substitutions`_: ``|id|``.
- In the src tree the only files (not folders), starting with ``_``, are generated ones.

See the example created with ``--init`` at the end of this file.

.. _`substitutions`: http://docutils.sourceforge.net/docs/ref/rst/directives.html#replacement-text

"""

import sys
import os
import re
from pathlib import Path
from urllib import request
import string
from functools import lru_cache
from collections import OrderedDict,defaultdict
from itertools import chain, tee
from types import GeneratorType

Tee = tee([], 1)[0].__class__
def memoized(f):
    cache={}
    def ret(*args):
        if args not in cache:
            cache[args]=f(*args)
        if isinstance(cache[args], (GeneratorType, Tee)):
            cache[args], r = tee(cache[args])
            return r
        return cache[args]
    return ret

verbose = False
_stpl = '.stpl'

rextitle = re.compile(r'^([!"#$%&\'()*+,\-./:;<=>?@[\]^_`{|}~])\1+$')
rexitem = re.compile(r'^:?(\w[^:]*):\s.*$')
rexname = re.compile(r'^\s*:name:\s*(\w.*)*$')
reximg = re.compile(r'image:: ((?:\.|/|\\|\w).*)')
#reximg.search('.. image:: ..\img.png').group(1)
#reximg.search(r'.. |c:\x y\im.jpg| image:: /tmp/img.png').group(1)
#reximg.search(r'.. image:: c:\tmp\img.png').group(1)
#reximg.search(r'.. image:: \\public\img.png').group(1)

#>>>> nj
nj = lambda *x:os.path.normpath(os.path.join(*x))

#>>>> rindices
def rindices(r,lns):
  """Return the indices matching a regular expression
  >>> lns=['a','ab','b','aa']
  >>> [lns[i] for i in rindices(r'^a\w*',lns)]==['a', 'ab', 'aa']
  True
  """
  if isinstance(r,str):
    r = re.compile(r)
  return filter(lambda x:r.search(lns[x]),range(len(lns)))

#>>>> rlines
def rlines(r,lns):
  return [lns[i] for i in rindices(r,lns)]

#>>>> intervals
"""
>>> intervals([1,2,3])==[(1, 2), (2, 3)]
True
"""
intervals = lambda it: list(zip(it[:],it[1:]))

#>>>> in2s
"""
>>> in2s([1,2,3,4])==[(1, 2), (3, 4)]
True
"""
in2s = lambda it: list(zip(it[::2],it[1::2]))

@lru_cache()
def read_lines(fn):
    lns = []
    with open(fn,'r',encoding='utf-8') as f:
        lns = f.readlines()
    return lns

is_rest = lambda x: x.endswith('.rest') or x.endswith('.rest'+_stpl)
is_rst = lambda x: x.endswith('.rst') or x.endswith('.rst'+_stpl)
@memoized
def genrstincluded(fn,paths=(),withimg=False):
    """return recursively all files included from an rst file"""
    for p in paths:
        nfn = os.path.normpath(os.path.join(p,fn))
        if os.path.exists(nfn):
            break
        elif os.path.exists(nfn+_stpl):
            nfn = nfn+_stpl
            break
    else:
        nfn = fn
    yield fn
    lns = read_lines(nfn)
    toctree = False
    if lns:
        for e in lns:
            if toctree:
                toctreedone = False
                if e.startswith(' '):
                    fl=e.strip()
                    if fl.endswith('.rest') and os.path.exists(fl):
                        toctreedone = True
                        yield from genrstincluded(fl,paths)
                    continue
                elif toctreedone:
                    toctree = False
            if e.startswith('.. toctree::'):
                toctree = True
            elif e.startswith('.. '):
                #e = '.. include:: some.rst'
                #e = '.. image:: some.png'
                #e = '.. figure:: some.png'
                #e = '.. |x y| image:: some.png'
                try:
                    f,t=e[3:].split('include:: ')
                    nf = not f and t
                    if nf and not nf.startswith('_links_'):
                        yield from genrstincluded(nf.strip(),paths)
                except:
                    if withimg:
                        m = reximg.search(e)
                        if m:
                            yield m.group(1)

def genfldrincluded(
        directory='.'
        ,exclude_paths_substrings = ['_links_','index.rest']
        ):
    """ find all .rest files in ``directory``
    and all files recursively included
    excluding those that contain ``exclude_paths_substrings``
    """
    for p,ds,fs in os.walk(directory):
        for f in sorted(fs):
            if is_rest(f):
                pf=nj(p,f)
                if any([x in pf for x in exclude_paths_substrings]):
                    continue
                res = []
                for ff in genrstincluded(f,(p,)):
                    if any([x in ff for x in exclude_paths_substrings]):
                        continue
                    pth=nj(p,ff)
                    if any([x in pth for x in exclude_paths_substrings]):
                        continue
                    res.append(pth)
                yield res

def links(lns):
    r = re.compile(r'\|(\w+)\|')
    for i,ln in enumerate(lns):
        mo = r.findall(ln)
        for g in mo:
            yield i,g

g_counters=defaultdict(dict)
def linktargets(lns,docnumber):
    #docprefix = str(docnumber)+'.'
    #docnumber=0
    #list(linktargets(lns,docnumber))
    docprefix = ' '
    if docnumber not in g_counters:
        g_counters[docnumber] = {".. figure":1,".. math":1,".. table":1,".. code":1} #=list-table,code-block
    counters=g_counters[docnumber]
    itgts = rindices(r'^\.\. _`?(\w[^:`]*)`?:\s*$',lns)
    lenlns = len(lns)
    for i in itgts:
        #i=list(itgts)[0]
        tgt = lns[i].strip(' ._:`\n')
        lnkname = tgt
        for j in range(i+2,i+8):
            #j=i+3
            if j > lenlns-1:
                break
            lnj = lns[j]
            if rextitle.match(lnj):
                lnkname=lns[j-1].strip()
                break
            #lnj=":lnkname: words"
            itm = rexitem.match(lnj)
            if itm:
                lnkname, = itm.groups()
                break
            #j,lns=1,".. figure::\n  :name: lnkname".splitlines();lnj=lns[j]
            #j,lns=1,".. figure::\n  :name:".splitlines();lnj=lns[j]
            #j,lns=1,".. math::\n  :name: lnkname".splitlines();lnj=lns[j]
            itm = rexname.match(lnj)
            if itm:
                lnkname, = itm.groups()
                lnj1 = lns[j-1].split('::')[0].replace('list-table','table').replace('code-block','code')
                if not lnkname and lnj1 in counters:
                    lnkname = lnj1[3].upper()+lnj1[4:]+docprefix+str(counters[lnj1])
                    counters[lnj1]+=1
                    break
                elif lnkname:
                    lnkname = lnkname.strip()
                    break
                else:
                    lnkname = tgt
        yield i, tgt, lnkname

def gen(source,target=None,fun=None,**kw):
    """ take the gen[_fun] functions enclosed by #def gen[_fun] to create a new file.
    >>> source=[i+'\\n' for i in '''
    ...        #def gen(lns,**kw):
    ...        #  return [l.split('#@')[1] for l in rlines('^\s*#@',lns)]
    ...        #def gen
    ...        #@some lines
    ...        #@to extrace
    ...        '''.splitlines()]
    >>> [l.strip() for l in gen(source)]
    ['some lines', 'to extrace']
    """
    if isinstance(source,list):
        lns = source
        source = ""
    else:
        lns = []
        try:
            lns = read_lines(source)
        except:
            sys.stderr.write("ERROR: {} cannot be opened\n".format(source))
            return
    iblks = list(rindices(r'#def gen(\w*(lns,\*\*kw):)*',lns))
    py3 = '\n'.join([lns[k][lns[i].index('#')+1:] 
            for i,j in in2s(iblks) 
            for k in range(i,j)])
    eval(compile(py3,source+'#gen','exec'),globals())
    if fun:
        gened = eval('gen_'+fun+'(lns,**kw)')
    else:
        gened = []
        for i in iblks[0::2]:
            cd = re.split("#def |:",lns[i])[1]#gen(lns,**kw)
            gened += eval(cd)
    if target:
        drn = os.path.dirname(target)
        if drn and not os.path.exists(drn):
            os.makedirs(drn)
        with open(target,'w',encoding='utf-8') as o:
            o.write(''.join(gened))
    else:
        return list(gened)

def genfile(gf):
    genfilelns = read_lines(gf)
    for ln in genfilelns:
        if ln[0] != '#':
            try:
              f,t,d,a = [x.strip() for x in ln.split('|')]
              kw=eval(a)
              yield f,t,d,kw
            except: pass

def mkdir(ef):
    try:
        os.mkdir(ef)
    except:
        pass

def mktree(tree):
    """ Build a directory tree from a string as returned by the tree tool.

    For same level, identation must be the same.
    So don't start with '''a in the example below.

    In addition 
    
    leafs:

    - / or \\ to make a directory leaf

    - << to copy file from internet using http:// or locally using file:://

    - use indented lines as file content

    >>> tree=[l for l in '''
    ...          a
    ...          ├aa.txt
    ...            this is aa
    ...          └u.txt<<http://docutils.sourceforge.net/docs/user/rst/quickstart.txt
    ...          b
    ...          ├c
    ...          │└d/
    ...          ├e  
    ...          │└f.txt
    ...          └g.txt
    ...            this is g
    ...       '''.splitlines() if l.strip()]
    >>> True#mktree(tree) 
    True
    """
    ct = re.search(r'[^\s├│└]',tree[0]).span()[0]
    t1 = [t[ct:] for t in tree]
    entry_re = re.compile(r'^(\w[^ </\\]*)(\s*<<\s*|\s*[\\/]\s*)*(\w.*)*')
    it1 = list(rindices(entry_re,t1))
    lt1 = len(t1)
    it1.append(lt1)
    for c,f in intervals(it1):
        ef,ed,eg = entry_re.match(t1[c]).groups()
        if ef:
            if c<f-1:
                i1 = t1[c+1].find('└')+1
                i2 = t1[c+1].find('├')+1
                ix = (i1>=0 and i1 or i2)-1
                if ix >= 0 and ix <= len(ef):
                    mkdir(ef)
                    old = os.getcwd()
                    os.chdir(ef)
                    mktree(
                      t1[c+1:f]
                      )
                    os.chdir(old)
                else:
                    t0 = t1[c+1:f]
                    ct = re.search(r'[^\s│]',t0[0]).span()[0]
                    tt = [t[ct:]+'\n' for t in t0]
                    with open(ef,'w') as fh:
                        fh.writelines(tt)
            elif eg:
                request.urlretrieve(eg,ef)
            elif ed and (('\\' in ed) or ('/' in ed)):
                mkdir(ef)
            else:
                Path(ef).touch()

def tree(path, with_content=False, with_files=True, with_dot_files=True, max_depth=100):
    """ inverse of mktree
    like the linux tree tool
    but optionally with content of files
    >>> path='.'
    >>> tree(path,False)
    >>> tree(path,True)

    """
    subprefix = ['│  ', '   '] 
    entryprefix = ['├─', '└─']
    def _tree(path, prefix):
        for p,ds,fs in os.walk(path):
            #p,ds,fs = path,[],os.listdir()
            lends = len(ds)
            lenfs = len(fs)
            if len(prefix)/3 >= max_depth:
                return
            for i,d in enumerate(sorted(ds)):
                yield prefix + entryprefix[i==lends+lenfs-1] + d
                yield from _tree(os.path.join(p,d),prefix+subprefix[i==lends+lenfs-1])
            del ds[:]
            if with_files:
                for i,f in enumerate(sorted(fs)):
                    if with_dot_files or not f.startswith('.'):
                        yield prefix + entryprefix[i==lenfs-1] + f
                        if with_content:
                            for ln in read_lines(os.path.join(p,f)):
                                yield prefix + subprefix[1] + ln
    return '\n'.join(_tree(path, ''))


def genfldrs(scanroot='.'):
    odir = os.getcwd()
    os.chdir(scanroot)
    fldr_lnktgts = OrderedDict()
    fldr_allfiles = defaultdict(set) #fldr, files
    fldr_alltgts = defaultdict(set) #all link target ids
    dcns=set([])
    for dcs in genfldrincluded('.'): 
        rest = [adc for adc in dcs if is_rest(adc)][0]
        fldr,fln = os.path.split(rest)
        fldr_allfiles[fldr] |= set(dcs)
        restn=os.path.splitext(fln)[0]
        if is_rest(restn):
            restn=os.path.splitext(restn)[0]
        dcns.add(restn)
        for doc in dcs:
            try: #generated files might not be there
                lns = read_lines(doc)
                lnks = list(links(lns))
                tgts = list(linktargets(lns,len(dcns)))
                if fldr not in fldr_lnktgts:
                    fldr_lnktgts[fldr] = []
                fldr_lnktgts[fldr].append((restn,doc,len(lns),lnks,tgts))
                fldr_alltgts[fldr] |= set([n for ni,n,nn in tgts])
            except:
                pass
    for fldr,lnktgts in fldr_lnktgts.items():
        allfiles = fldr_allfiles[fldr]
        alltgts = fldr_alltgts[fldr]
        yield fldr, (lnktgts,allfiles,alltgts)
    os.chdir(odir)

doctypes = "sphinx docx pdf".split()
def lnksandtags(fldr,lnktgts,allfiles,alltgts):
    _tgtsdoc = [(dt,[]) for dt in doctypes]
    tags = []
    orestn = None
    up = 0
    if (fldr.strip()):
       up = len(fldr.split(os.sep))
    #unknowntgts = []
    for restn, doc, lenlns, lnks, tgts in lnktgts:
         fin = doc.replace("\\","/")
         if restn != orestn:
             orestn = restn
             if verbose:
                 print('    '+restn+'.rest')
         if not is_rest(doc):
             if verbose:
                 print('        '+doc)
         for _,di in _tgtsdoc:
             di.append('\n.. .. {0}\n\n'.format(fin))
         iterlnks = iter(lnks)
         def add_linksto(i,ojlnk=None):
             linksto = []
             if ojlnk and ojlnk[0] < i:
                 if ojlnk[1] in alltgts:
                     linksto.append(ojlnk[1])
                 else:
                     linksto.append('-'+ojlnk[1])
                     #unknowntgts.append(ojlnk[1])
                 ojlnk = None
             if ojlnk is None:
                 for j, lnk in iterlnks:
                     if j > i:#links up to this target
                         ojlnk = j,lnk
                         break
                     else:
                         if lnk in alltgts:
                             linksto.append(lnk)
                         else:
                             linksto.append('-'+lnk)
                             #unknowntgts.append(lnk)
             if linksto:
                 linksto = '.. .. ' + ','.join(linksto) + '\n\n'
                 for _,ddi in _tgtsdoc:
                     ddi.append(linksto)
             return ojlnk
         ojlnk=None
         for i,tgt,lnkname in tgts:
             ojlnk = add_linksto(i,ojlnk)
             for ddn,ddi in _tgtsdoc:
                 if ddn=='sphinx':
                     tgte = ".. |{0}| replace:: :ref:`{1}<{0}>`\n".format(tgt,lnkname)
                 elif ddn=='docx':
                     tgte = ".. |{0}| replace:: `{1} <{2}#{0}>`_\n".format(tgt,lnkname,restn+'.docx')
                 elif ddn=='pdf':
                     tgte = ".. |{0}| replace:: `{1} <{2}#{0}>`_\n".format(tgt,lnkname,restn+'.pdf')
                 ddi.append(tgte)
             tags.append('{0}	{1}	/^\.\. _`\?{0}`\?:/;"		line:{2}'.format(tgt,"../"*up+fin,i+1))
         ojlnk = add_linksto(lenlns,ojlnk)
    for ddn,ddi in _tgtsdoc:
        with open(nj(fldr,'_links_%s.rst'%ddn),'w',encoding='utf-8') as f:
            f.write('\n'.join(ddi));
    with open(nj(fldr,'.tags'),'wb') as f:
        f.write('\n'.join(tags).encode('utf-8'));

#==============> for building with WAF

try:
    from waflib import TaskGen, Task
    import bottle

    gensrc={}
    @TaskGen.feature('gen_files')
    @TaskGen.before('process_rule')
    def gen_files(self):
        global gensrc
        gensrc={}
        for f,t,fun,kw in genfile(self.path.make_node('gen').abspath()):
            gensrc[t]=f
            frm = self.path.find_resource(f)
            twd = self.path.make_node(t)
            self.create_task('gentsk',frm,twd,fun=fun,kw=kw)
    class gentsk(Task.Task):
        def run(self):
            try:
                frm = self.inputs[0]
                twd = self.outputs[0]
                twd.parent.mkdir()
                gen(frm.abspath(),twd.abspath(),fun=self.fun,**self.kw)
            except: pass
    def get_docs(self):
        docs = [x.lower() for x in self.bld.options.docs]
        if not docs:
            docs = [x.lower() for x in self.env.docs]
        return docs
    @TaskGen.feature('gen_links')
    @TaskGen.before('process_rule')
    def gen_links(self):
        def fldrscan():
            deps = []
            for rest in self.path.ant_glob(['*.rest','*.rest'+_stpl]):
                if not rest.name.startswith('index'):
                    fles = genrstincluded(rest.name,(rest.parent.abspath(),))
                    for x in fles:
                        isrst = is_rst(x)
                        if isrst and x.startswith('_links_'):#else cyclic dependency for _links_xxx.rst
                            continue
                        nd = self.path.find_node(x)
                        if not nd:
                            if isrst and not x.endswith(_stpl):
                                nd = self.path.find_node(x+_stpl)
                        deps.append(nd)
            depsgensrc = [self.path.find_node(gensrc[x]) for x in deps if x and x in gensrc] 
            rs = [x for x in deps if x]+depsgensrc
            return (rs,[])
        docs=get_docs(self)
        if docs:
            linksandtags = [self.path.make_node(x) for x in ['_links_'+x+'.rst' for x in doctypes]+['.tags']]
            self.create_task('rstindex',self.path,linksandtags,scan=fldrscan)
    class rstindex(Task.Task):
        def run(self):
            for fldr, (lnktgts,allfiles,alltgts) in genfldrs(self.inputs[0].abspath()):
                lnksandtags(fldr,lnktgts,allfiles,alltgts)
    @TaskGen.extension('.rest')
    def gendoc(self,node):
        def rstscan():
            srcpath = node.parent.get_src()
            orgd = node.parent.abspath()
            d = srcpath.abspath()
            n = node.name
            nod = None
            if node.is_bld() and not node.name.endswith(_stpl):
                nod = srcpath.find_node(node.name+_stpl)
            if not nod:
                nod = node
            ch = genrstincluded(n,(d,orgd),True)
            deps = []
            nodeitself=True
            for x in ch:
                if nodeitself:
                    nodeitself = False
                    continue
                isrst = is_rst(x)
                if isrst and x.startswith('_links_'):#else cyclic dependency for _links_xxx.rst
                        continue
                nd = srcpath.find_node(x)
                if not nd:
                    if isrst and not x.endswith(_stpl):
                        nd = srcpath.find_node(x+_stpl)
                deps.append(nd)
            depsgensrc = [self.path.find_node(gensrc[x]) for x in deps if x and x in gensrc] 
            rs = [x for x in deps if x]+depsgensrc
            return (rs,[])
        docs=get_docs(self)
        linkdeps = [self.path.get_src().find_node(x) for x in ['_links_'+x+'.rst' for x in doctypes]]
        if node.name != "index.rest":
            if 'docx' in docs or 'defaults' in docs:
                out_node_docx = node.parent.find_or_declare('docx/'+node.name[:-len('.rest')]+'.docx')
                self.create_task('docx', [node]+linkdeps, out_node_docx, scan=rstscan)
            if 'pdf' in docs:
                out_node_pdf = node.parent.find_or_declare('pdf/'+node.name[:-len('.rest')]+'.pdf')
                self.create_task('pdf', [node]+linkdeps, out_node_pdf, scan=rstscan)
        else:
            if 'html' in docs:
                out_node_html = node.parent.get_bld()
                self.create_task('sphinx',[node]+linkdeps,out_node_html,cwd=node.abspath(),scan=rstscan)
    class pdfordocx(Task.Task):
        def run(self):
            from subprocess import Popen, PIPE
            frm = self.inputs[0].abspath()
            twd = self.outputs[0].abspath()
            dr = self.inputs[0].parent.get_src()
            refoption,refdoc,cmd,linksdoc = self.refdoc_cmd(twd)
            rd = dr.find_resource(refdoc) or dr.parent.find_resource(refdoc)
            if rd:
                cmd.append(refoption)
                cmd.append(rd.abspath())
            oldp = os.getcwd()
            os.chdir(dr.abspath())
            try:
                with open(frm,'rb') as f:
                    i1 = f.read().replace(b'\n.. include:: _links_sphinx.rst',b'')
                links_docx = dr.find_resource(linksdoc)
                with open(links_docx.abspath(),'rb') as f:
                    i2 = f.read()
                p = Popen(cmd, stdin=PIPE)
                p.stdin.write(i1)
                p.stdin.write(i2)
                p.stdin.close()    
                p.wait()
            finally:
                os.chdir(oldp)
    class pdf(pdfordocx):
        def refdoc_cmd(self,output):
            pandoc = ['pandoc','--listings','--number-sections', 
                '--pdf-engine','xelatex','-f', 'rst']+ list(chain.from_iterable(zip(['-V']*4,
                ['titlepage','papersize=a4','toc','toc-depth=3','geometry:margin=2.5cm']
                )))+ ['-o', output]
            return '--template','reference.tex', pandoc, '_links_pdf.rst'
    class docx(pdfordocx):
        def refdoc_cmd(self,output):
            pandoc = ['pandoc','-f', 'rst', '-t', 'docx', '-o', output]
            return '--reference-doc','reference.docx', pandoc, '_links_docx.rst'
    class sphinx(Task.Task):
        def run(self):
            from subprocess import run
            copies = []
            try:
                for x in self.inputs[0].read(encoding='utf-8').splitlines(True):
                    xf = x.strip()
                    xnew = None
                    if xf.endswith('.rest'):
                        xff = self.inputs[0].parent.find_node(xf)
                        if not xff:
                            xff = self.inputs[0].parent.get_bld().find_node(xf)
                            #need to copy to src a generated file
                            xffcopy = self.inputs[0].parent.make_node(xff.name)
                            copies.append(xffcopy)
                            xffcopy.write(xff.read(encoding='utf-8'),encoding='utf-8')
                dr = self.inputs[0].parent
                tgt = self.outputs[0].find_or_declare('html').abspath()
                confighere = dr.find_node('conf.py')
                if confighere:
                    run(['sphinx-build','-Ea', '-b', 'html',dr.abspath(),tgt])
                else:
                    configabove = dr.find_node('../conf.py')
                    if configabove:
                        run(['sphinx-build','-Ea', '-b', 'html',dr.abspath(),tgt,'-c',configabove.parent.abspath()])
                    else:
                        print('NO conf.py in '+dr.abspath()+' or above')
            finally:
                for c in copies:
                    c.delete()

    def options(opt):
        def docscb(option, opt, value, parser):
            setattr(parser.values, option.dest, value.split(','))
        opt.add_option("--docs", type='string', action="callback", callback= docscb, dest='docs', default=[],
            help="Like html,docx (default) or html,pdf or html,docx,pdf at configure or build (default None)") 

    def configure(cfg):
        cfg.env['docs'] = cfg.options.docs

    def build(bld):
        bld.src2bld = lambda f: bld(features='subst',source=f,target=f,is_copy=True)
        def gen_files():
            bld(features="gen_files")
            bld.add_group()
        bld.gen_files = gen_files
        def gen_links():
            bld(features="gen_links")
            bld.add_group()
        bld.gen_links = gen_links
        def build_docs():
            bld(source=[x for x in bld.path.ant_glob(['*.rest','*.rest'+_stpl])])
        bld.build_docs = build_docs
        def stpl(tsk):
            bldpath = bld.path.get_bld()
            ps = tsk.inputs[0].abspath()
            pt = tsk.outputs[0].abspath()
            lookup,name=os.path.split(ps)
            env = tsk.env
            env.update(tsk.generator.__dict__)
            st=bottle.template(name
                    ,template_lookup = [lookup]
                    ,bldpath = bldpath.abspath()
                    ,options = bld.options
                    ,**env
                    ) 
            with open(pt,mode='w',encoding="utf-8",newline="\n") as f: 
                f.write(st)
        bld.stpl=stpl
        bld.declare_chain('stpl',ext_in=[_stpl],ext_out=[''],rule=stpl)

except:
    pass

#==============< for building with WAF

#this is for mktree(): first line of file content must not be empty!
example_tree = r'''
       src
        ├ dcx.py << file:///__file__
        ├ code
        │   └ some.h
                /*
                #def gen_tst(lns,**kw):
                #  return [l.split('@')[1] for l in rlines('^\s*@',lns)]
                #def gen_tst
                #def gen_tstdoc(lns,**kw):
                #  return ['#) '+l.split('**')[1] for l in rlines('^/\*\*',lns)]
                #def gen_tstdoc

                @//generated from some.h
                @#include <assert.h>
                @#include "some.h"
                @int main()
                @{
                */

                /**Test add1()
                @assert(add1(1)==2);
                */
                int add1(int a)
                {
                  return a+1;
                }

                /**Test add2()
                @assert(add2(1)==3);
                */
                int add2(int a)
                {
                  return a+2;
                }

                /*
                @}
                */
        ├ wscript
            from waflib import Logs
            Logs.colors_lst['BLUE']='\x1b[01;36m'

            top='.'
            out='../build'

            def options(opt):
              opt.load('dcx',tooldir='.')

            def configure(cfg):
              cfg.load('dcx',tooldir='.')
              
            def build(bld):
              #defines bld.stpl(), bld.gen_files(), bld.gen_links(), bld.build_docs()
              bld.load('dcx',tooldir='.')
              bld.recurse('doc')

        └ doc
           ├ wscript_build
           │    bld.gen_files()
           │    bld.gen_links()
           │    bld.build_docs()
           ├ _static
           │    └ img.png << https://assets-cdn.github.com/images/modules/logos_page/Octocat.png
           ├ index.rest
           │  ============
           │  Project Name
           │  ============
           │
           │  .. toctree::
           │     ra.rest
           │     sr.rest
           │     dd.rest
           │     tp.rest
           │
           ├ ra.rest
           │  Risk Analysis
           │  =============
           │  
           │  .. _`rz7`:
           │  
           │  rz7: risk calculations
           │  
           │  Risk analysis could be a SimpleTemplate (.stpl) file,
           │  where calculation are done in python while converting to this file.
           │  
           │  Similarly one can have a 
           │  
           │  - is.rest for issues
           │  
           │  - pp.rest for the project plan 
           │    (with backlog, epics, stories, tasks) 
           │  
           │  .. include:: _links_sphinx.rst
           │  
           ├ sr.rest
           │  Software/System Requirements
           │  ============================
           │
           │  Requirements mostly phrased as tests (see |t9a|). 
           │
           │  .. _`sy7`:
           │
           │  A Requirement Group
           │  -------------------
           │
           │  .. _`s3a`:
           │
           │  s3a: brief description
           │
           │  Don't count the ID, since the order will change.
           │  Instead: The IDs have the first letter of the file 
           │  and 2 or more random letters of ``[0-9a-z]``.
           │  Use an editor macro to generate IDs.
           │
           │  Every ``.rest`` has this line at the end::
           │  
           │     .. include:: _links_sphinx.rst
           │  
           │  .. include:: _links_sphinx.rst
           │  
           ├ dd.rest
           │  Design Description
           │  ==================
           │  
           │  ``dcx.py`` produces its own labeling consistent across DOCX, PDF, HTML,
           │  and same as Sphinx (useful for display math). 
           │  
           │  .. _`dz7`:
           │  
           │  dz7: Independent DD IDs
           │  
           │    The relation with RS IDs is m-n. Links like |s3a|
           │    can be scattered over more DD entries.  
           │  
           │  .. _`dz3`:
           │  
           │  .. figure:: _static/img.png
           │     :name:
           │  
           │     |dz3|: Caption here.
           │  
           │     The usage of ``:name:`` produces: ``WARNING: Duplicate explicit target name: ""``. Ignore.
           │  
           │  Reference via |dz3|.
           │  
           │  .. _`dta`:
           │  
           │  |dta|: Table legend
           │  
           │  .. list-table::
           │     :name:
           │     :widths: 20 80
           │     :header-rows: 1
           │  
           │     * - Bit
           │       - Function
           │  
           │     * - 0
           │       - xxx
           │  
           │  Reference |dta| does not show ``dta``.
           │  
           │  .. _`dyi`:
           │  
           │  |dyi|: Listing showing struct.
           │  
           │  .. code-block:: cpp
           │     :name:
           │  
           │     struct xxx{
           │        int yyy; //yyy for zzz
           │     }
           │  
           │  Reference |dyi| does not show ``dyi``.
           │  
           │  .. _`d9x`:
           │  
           │  .. math:: 
           │     :name:
           │  
           │     V = \frac{K}{r^2}
           │  
           │  Reference |d9x| does not show ``d9x``.
           │  
           │  .. _`d99`:
           │  
           │  OtherName: Keep names the same all over.
           │  
           │  Here instead of ``d99:`` we use ``:OtherName:``, but now we have two synonyms for the same item.
           │  This is no good. If possible, keep ``d99`` in the source and in the final docs.
           │  
           │  Reference |d99| does not show ``d99``.
           │  
           │  The item target must be in the same file as the item content. The following would not work::
           │  
           │    .. _`dh5`:
           │    
           │    .. include:: somefile.rst   
           │  
           │  .. include:: _links_sphinx.rst
           │  
           ├ tp.rest
           │   Test Plan
           │   =========
           │   
           │   .. _`t9a`:
           │   
           │   Requirement Tests
           │   -----------------
           │
           │   No duplication. Only reference the requirements to be tested.
           │
           │   - |s3a|
           │
           │   Or better: reference the according SR chapter, else changes there would need an update here.
           │
           │   - Test |sy7|
           │
           │   Unit Tests
           │   ----------
           │
           │   Use ``.rst`` for included files and start the file with ``_`` if generated.
           │   
           │   .. include:: _sometst.rst
           │
           │   .. include:: _links_sphinx.rst
           │
           ├ gen
              #from|to|gen_xxx|kwargs
              ../code/some.h | _sometst.rst                | tstdoc | {}
              ../code/some.h | ../../build/code/some_tst.c | tst    | {}
           ├ conf.py
              extensions = ['sphinx.ext.autodoc',
                  'sphinx.ext.todo',
                  'sphinx.ext.mathjax',
                  'sphinx.ext.viewcode',
                  'sphinx.ext.graphviz',
                  ]
              numfig = False
              templates_path = ['_templates']
              source_suffix = '.rest'
              master_doc = 'index'
              project = 'docxsample'
              author = project+' Project Team'
              copyright = '2017, '+author
              version = '1.0'
              release = '1.0.0'
              language = None
              exclude_patterns = []
              pygments_style = 'sphinx'
              todo_include_todos = True
              import sphinx_bootstrap_theme
              html_theme = 'bootstrap'
              html_theme_path = sphinx_bootstrap_theme.get_html_theme_path()
              latex_elements = {
                      'preamble':r"""
                      \usepackage{caption}
                      \captionsetup[figure]{labelformat=empty}
                      """
                      }
              latex_documents = [
                  (master_doc, 'docxsample.tex', project+' Documentation',
                   author, 'manual'),
              ]
           └ Makefile
              SPHINXOPTS    = 
              SPHINXBUILD   = sphinx-build
              SPHINXPROJ    = docxsmpl
              SOURCEDIR     = .
              BUILDDIR      = ../../build/doc
              .PHONY: docx help Makefile docxdir pdfdir index
              docxdir: ${BUILDDIR}/docx
              pdfdir: ${BUILDDIR}/pdf
              MKDIR_P = mkdir -p
              ${BUILDDIR}/docx:
              	${MKDIR_P} ${BUILDDIR}/docx
              ${BUILDDIR}/pdf:
              	${MKDIR_P} ${BUILDDIR}/pdf
              index:
              	python ..\dcx.py
              help:
              	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
              	@echo "  docx        to docx"
              	@echo "  pdf         to pdf"
              %: Makefile index
              	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
              docx: docxdir index
              	cat sr.rest _links_docx.rst | sed -e's/^.. include:: _links_sphinx.rst//g' | pandoc -f rst -t docx -o "$(BUILDDIR)/docx/sr.docx"
              	cat dd.rest _links_docx.rst | sed -e's/^.. include:: _links_sphinx.rst//g' | pandoc -f rst -t docx -o "$(BUILDDIR)/docx/dd.docx"
              	cat tp.rest _links_docx.rst | sed -e's/^.. include:: _links_sphinx.rst//g' | pandoc -f rst -t docx -o "$(BUILDDIR)/docx/tp.docx"
              	cat ra.rest _links_docx.rst | sed -e's/^.. include:: _links_sphinx.rst//g' | pandoc -f rst -t docx -o "$(BUILDDIR)/docx/ra.docx"
              pdf: pdfdir index
              	cat sr.rest _links_pdf.rst | sed -e's/^.. include:: _links_sphinx.rst//g' | pandoc -f rst --pdf-engine xelatex --number-sections -V papersize=a4 -V toc -V toc-depth=3 -V geometry:margin=2.5cm -o "$(BUILDDIR)/pdf/sr.pdf"
              	cat dd.rest _links_pdf.rst | sed -e's/^.. include:: _links_sphinx.rst//g' | pandoc -f rst --pdf-engine xelatex --number-sections -V papersize=a4 -V toc -V toc-depth=3 -V geometry:margin=2.5cm -o "$(BUILDDIR)/pdf/dd.pdf"
              	cat tp.rest _links_pdf.rst | sed -e's/^.. include:: _links_sphinx.rst//g'  | pandoc -f rst --pdf-engine xelatex --number-sections -V papersize=a4 -V toc -V toc-depth=3 -V geometry:margin=2.5cm -o "$(BUILDDIR)/pdf/tp.pdf"
              	cat ra.rest _links_pdf.rst | sed -e's/^.. include:: _links_sphinx.rst//g' | pandoc -f rst --pdf-engine xelatex --number-sections -V papersize=a4 -V toc -V toc-depth=3 -V geometry:margin=2.5cm -o "$(BUILDDIR)/pdf/ra.pdf"
       build/
'''

def main(**args):
  import codecs
  import argparse

  if not args:
    parser = argparse.ArgumentParser(description='''Sample RST Documentation for HTML and DOCX.
      Creates |substitution| links and ctags for link targets.
      ''')
    parser.add_argument('--init', dest='root', action='store',
                        help='''create a sample folder structure. 
                        Afterwards run "make html" or "make docx" form "doc" folder.''')
    parser.add_argument('-v','--verbose', action='store_true',
                        help='''Show files recursively included by each rest''')
    args = parser.parse_args().__dict__

  iroot = args['root']
  global verbose
  verbose = args['verbose']
  if iroot:
    thisfile = str(Path(__file__).resolve()).replace('\\','/')
    tree=[l for l in example_tree.replace('__file__',thisfile).splitlines() if l.strip()]
    mkdir(iroot)
    oldd = os.getcwd()
    os.chdir(iroot)
    mktree(tree)
    os.chdir(oldd)
  else:
    #link, gen and tags per folder
    for fldr, (lnktgts,allfiles,alltgts) in genfldrs('.'):
        if verbose:
            print(fldr)
        #generate files
        gf = nj(fldr,'gen')
        if os.path.exists(gf):
            for f,t,d,kw in genfile(gf):
                gen(nj(fldr,f),target=nj(fldr,t),fun=d,**kw)
        lnksandtags(fldr,lnktgts,allfiles,alltgts)

if __name__=='__main__':
  main()

