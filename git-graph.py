#!/usr/bin/env python3.5

import collections
from graphviz import Digraph
import os
import subprocess

from typing import Dict, Tuple, List

# Git object types.
Branch = collections.namedtuple('Branch', 'name commit')
Commit = collections.namedtuple('Commit', 'hash tree parent')
Tree = collections.namedtuple('Tree', 'hash name trees blobs')
Blob = collections.namedtuple('Blob', 'hash name')

Hash = str

git_dir = os.path.join(os.getcwd(), '.git')

graph = Digraph(comment='Git graph')
graph.attr(compound='true')
graph.attr('graph', splines='true')

# object cache: hash -> object (commit, tree, blob).
cache = {} # type: Dict[Hash, object]

branch_to_commit = {} # type: Dict[str, List[Hash]]
commit_to_parents = {} # type: Dict[Hash, List[Hash]]
commit_to_tree = {} # type: Dict[Hash, Hash]
tree_to_trees = {} # type: Dict[Hash, List[Hash]]
tree_to_blobs = {} # type: Dict[Hash, List[Hash]]
blobs = {} # type: Dict[Hash, Blob]

def add_to_multimap(multimap: Dict[str, List[str]], key: str, value: str):
  if key not in multimap:
    multimap[key] = []
  if value not in multimap[key]:
    multimap[key].append(value)

# Lists all the branches of the git repo.
def list_branches() -> List[Branch]:
  heads_dir = os.path.join(git_dir, 'refs', 'heads')
  files = os.listdir(heads_dir)
  return [Branch(name=f, commit=read_txt(os.path.join(heads_dir, f))) for f in files]

# Traverses the history of a commit.
def traverse_history(commit_hash: Hash):
    commit = get_commit(commit_hash)
    while commit.parent:
      parent_commit = get_commit(commit.parent)
      add_to_multimap(commit_to_parents, commit.hash, parent_commit.hash)
      commit = parent_commit

# Gets the commit by its hash.
def get_commit(hash: Hash) -> Commit:
  if hash not in cache:
    content = git_cat_file(hash)
    commit = parse_commit(hash, content)
    cache[hash] = commit
    tree = get_tree(commit.tree)
    commit_to_tree[commit.hash] = tree.hash
  return cache[hash]

def parse_commit(hash: Hash, content: str) -> Commit:
  lines = content.split('\n')
  dict = {'hash' : hash, 'tree' : None, 'parent' : None}
  for line in lines:
    if not line:
      continue
    parts = line.split()
    if len(parts) < 2 or parts[0] not in ['hash', 'tree', 'parent']:
      continue
    dict[parts[0]] = ' '.join(parts[1:])
  return Commit(**dict)

# Gets the tree by its hash.
def get_tree(hash: Hash, name='/') -> Commit:
  if hash not in cache:
    content = git_cat_file(hash)
    tree = parse_tree(hash, name, content)
    for child_hash in tree.blobs:
      add_to_multimap(tree_to_blobs, hash, child_hash)
    for child_hash in tree.trees:
      add_to_multimap(tree_to_trees, hash, child_hash)
    cache[hash] = tree
  return cache[hash]

def parse_tree(hash: Hash, name: str, content: str) -> Tree:
  lines = content.split('\n')
  dict = {'hash' : hash, 'name': name, 'trees' : [], 'blobs' : []}
  for line in lines:
    if not line:
      continue
    # mode type hash name
    mode, type, child_hash, child_name = line.split()
    if type == 'tree':
      get_tree(child_hash, child_name)
      dict['trees'].append(child_hash)
    elif type == 'blob':
      dict['blobs'].append(child_hash)
      blobs[child_hash] = Blob(hash=child_hash, name=child_name)
  return Tree(**dict)

def git_cat_file(hash: Hash):
  returncode, out, err = run_command('git cat-file -p {}'.format(hash))
  if returncode:
    raise Exception('Object {} not found.'.format(hash))
  return out.decode('utf-8')

def run_command(command: str):
  proc = subprocess.Popen([command], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
  out, err = proc.communicate()
  return proc.returncode, out, err

def read_txt(file_path: str):
  with open(file_path, 'r') as f:
      return f.read().replace('\n', '')

def check_prerequisites():
  pass

def get_display_name_for_blob(blob: Blob):
  return blob.name + ' ' + blob.hash[:6]

def get_display_name_for_tree(tree: Tree):
  return tree.name + ' ' + tree.hash[:6]

def main():
  check_prerequisites()
  branches = list_branches()
  for branch in branches:
    branch_to_commit[branch.name] = branch.commit
    traverse_history(branch.commit)
  print(branch_to_commit)
  print(commit_to_parents)
  print(commit_to_tree)
  print(tree_to_trees)
  print(tree_to_blobs)
  print(blobs)
  with graph.subgraph(name='cluster_blobs') as subgraph:
    subgraph.attr(label='Blobs', color='gray')
    for hash in blobs:
      subgraph.node(get_display_name_for_blob(blobs[hash]), shape='ellipse', style='filled', color='lightgray')
  with graph.subgraph(name='cluster_trees') as subgraph:
    subgraph.attr(label='Trees', color='gray')
    for hash in tree_to_blobs:
      tree = get_tree(hash)
      tree_display_name = get_display_name_for_tree(tree)
      subgraph.node(tree_display_name, shape='triangle')
      for blob_hash in tree_to_blobs[hash]:
        subgraph.edge(tree_display_name, get_display_name_for_blob(blobs[blob_hash]))
    for hash in tree_to_trees:
      tree = get_tree(hash)
      subgraph.node(get_display_name_for_tree(tree), shape='triangle')
      for subtree_hash in tree_to_trees[hash]:
        subtree = get_tree(subtree_hash)
        subgraph.edge(get_display_name_for_tree(tree), get_display_name_for_tree(subtree))
  with graph.subgraph(name='cluster_commits') as subgraph:
    subgraph.attr(label='Commits', color='gray')
    for hash in commit_to_tree:
      subgraph.node(hash[:6], shape='rectangle', style='filled', color='lightgray')
      tree = get_tree(commit_to_tree[hash])
      subgraph.edge(hash[:6], get_display_name_for_tree(tree))
    for hash in commit_to_parents:
      for parent_commit in commit_to_parents[hash]:
        subgraph.edge(hash[:6], parent_commit[:6])
  with graph.subgraph(name='cluster_branches') as subgraph:
    subgraph.attr(label='Branches', color='gray')
    for branch in branch_to_commit:
      subgraph.node(branch, shape='parallelogram')
      subgraph.edge(branch, branch_to_commit[branch][:6])

  print(graph.source)
  graph.render('git.gv', view=True)


if __name__ == '__main__':
  main()
