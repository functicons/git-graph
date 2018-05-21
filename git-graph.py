#!/usr/bin/env python3

# Script for generating the graph for the data model of a Git repository.
#
# Requirements: Python 3.5+, graphviz.
#
# Usage: python3.5 git-graph.py [git-repo-path]

import collections
from graphviz import Digraph
import os
import shutil
import subprocess
import sys

from typing import Dict, Tuple, List, Set

# Git object types.
Branch = collections.namedtuple('Branch', 'name commit')
Commit = collections.namedtuple('Commit', 'hash tree parents')
Tree = collections.namedtuple('Tree', 'hash name trees blobs')
Blob = collections.namedtuple('Blob', 'hash name')
Hash = str

# Data model of a Git repository.
class GitRepo:
  def __init__(self, git_repo_path):
    self.git_repo_path = git_repo_path
    self.dot_git_dir = os.path.join(git_repo_path, '.git')
    # object cache: hash -> object (commit, tree, blob).
    self.cache = {}  # type: Dict[Hash, object]
    self.branches = [] # type: List[str]
    self.branch_to_commit = {}  # type: Dict[str, List[Hash]]
    self.commit_to_parents = {}  # type: Dict[Hash, List[Hash]]
    self.commit_to_tree = {}  # type: Dict[Hash, Hash]
    self.tree_to_trees = {}  # type: Dict[Hash, List[Hash]]
    self.tree_to_blobs = {}  # type: Dict[Hash, List[Hash]]
    self.blobs = {}  # type: Dict[Hash, Blob]

  # Parses the .git directory and creates the in-memory data structure for it.
  def parse_dot_git_dir(self):
    self.branches = self.list_branches()
    for branch in self.branches:
      self.branch_to_commit[branch.name] = branch.commit
      self.traverse_history(branch.commit)

  # Lists all the branches of the git repo.
  def list_branches(self) -> List[Branch]:
    heads_dir = os.path.join(self.dot_git_dir, 'refs', 'heads')
    files = os.listdir(heads_dir)
    return [Branch(name=f, commit=self.read_txt(os.path.join(heads_dir, f))) for f in files]

  # Traverses the history of a commit.
  def traverse_history(self, commit_hash: Hash, visited: Set[Hash] = set()):
    if commit_hash in visited:
      return
    visited.add(commit_hash)
    commit = self.get_commit(commit_hash)
    for parent_hash in commit.parents:
      self.add_to_multimap(
          self.commit_to_parents, commit_hash, parent_hash)
      self.traverse_history(parent_hash, visited)

  # Gets the commit by its hash.
  def get_commit(self, hash: Hash) -> Commit:
    if hash not in self.cache:
      content = self.git_cat_file(hash)
      commit = self.parse_commit(hash, content)
      self.cache[hash] = commit
      tree = self.get_tree(commit.tree)
      self.commit_to_tree[commit.hash] = tree.hash
    return self.cache[hash]

  def parse_commit(self, hash: Hash, content: str) -> Commit:
    lines = content.split('\n')
    dict = {'hash': hash, 'tree': None, 'parents': []}
    for line in lines:
      if not line:
        continue
      parts = line.split()
      if len(parts) < 2:
        continue
      if parts[0] == 'tree':
        dict['tree'] = parts[1]
      elif parts[0] == 'parent':
        dict['parents'].append(parts[1])
    return Commit(**dict)

  # Gets the tree by its hash.
  def get_tree(self, hash: Hash, name='/') -> Commit:
    if hash not in self.cache:
      content = self.git_cat_file(hash)
      tree = self.parse_tree(hash, name, content)
      for child_hash in tree.blobs:
        self.add_to_multimap(self.tree_to_blobs, hash, child_hash)
      for child_hash in tree.trees:
        self.add_to_multimap(self.tree_to_trees, hash, child_hash)
      self.cache[hash] = tree
    return self.cache[hash]

  def parse_tree(self, hash: Hash, name: str, content: str) -> Tree:
    lines = content.split('\n')
    dict = {'hash': hash, 'name': name, 'trees': [], 'blobs': []}
    for line in lines:
      if not line:
        continue
      # mode type hash name
      mode, type, child_hash, child_name = line.split()
      if type == 'tree':
        self.get_tree(child_hash, child_name)
        dict['trees'].append(child_hash)
      elif type == 'blob':
        dict['blobs'].append(child_hash)
        self.blobs[child_hash] = Blob(hash=child_hash, name=child_name)
    return Tree(**dict)

  def git_cat_file(self, hash: Hash):
    returncode, out, err = self.run_command(
        command='git cat-file -p {}'.format(hash),
        current_dir=self.git_repo_path)
    if returncode:
      raise Exception('Object {} not found.'.format(hash))
    return out.decode('utf-8')

  def run_command(self, command: str, current_dir: str = os.getcwd()):
    proc = subprocess.Popen(
        [command], cwd=current_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    out, err = proc.communicate()
    return proc.returncode, out, err

  def read_txt(self, file_path: str):
    with open(file_path, 'r') as f:
      return f.read().replace('\n', '')

  def add_to_multimap(self, multimap: Dict[str, List[str]], key: str, value: str):
    if key not in multimap:
      multimap[key] = []
    if value not in multimap[key]:
      multimap[key].append(value)

# Graph generator for a git repository.
class GraphGenerator:
  def generate_graph(self, git_repo):
    graph = Digraph(comment='Git graph')
    graph.attr(compound='true')
    graph.attr('graph', splines='true')

    with graph.subgraph(name='cluster_blobs') as subgraph:
      subgraph.attr(label='Blobs', color='gray')
      for hash in git_repo.blobs:
        subgraph.node(self.get_display_name_for_blob(
            git_repo.blobs[hash]), shape='ellipse', style='filled', color='lightgray')
    with graph.subgraph(name='cluster_trees') as subgraph:
      subgraph.attr(label='Trees', color='gray')
      for hash in git_repo.tree_to_blobs:
        tree = git_repo.get_tree(hash)
        tree_display_name = self.get_display_name_for_tree(tree)
        subgraph.node(tree_display_name, shape='triangle')
        for blob_hash in git_repo.tree_to_blobs[hash]:
          subgraph.edge(tree_display_name,
                        self.get_display_name_for_blob(git_repo.blobs[blob_hash]))
      for hash in git_repo.tree_to_trees:
        tree = git_repo.get_tree(hash)
        subgraph.node(self.get_display_name_for_tree(tree), shape='triangle')
        for subtree_hash in git_repo.tree_to_trees[hash]:
          subtree = git_repo.get_tree(subtree_hash)
          subgraph.edge(self.get_display_name_for_tree(tree),
                        self.get_display_name_for_tree(subtree))
    with graph.subgraph(name='cluster_commits') as subgraph:
      subgraph.attr(label='Commits', color='gray')
      for hash in git_repo.commit_to_tree:
        subgraph.node(hash[:6], shape='rectangle',
                      style='filled', color='lightgray')
        tree = git_repo.get_tree(git_repo.commit_to_tree[hash])
        subgraph.edge(hash[:6], self.get_display_name_for_tree(tree))
      for hash in git_repo.commit_to_parents:
        for parent_commit in git_repo.commit_to_parents[hash]:
          subgraph.edge(hash[:6], parent_commit[:6])
    with graph.subgraph(name='cluster_branches') as subgraph:
      subgraph.attr(label='Branches', color='gray')
      for branch in git_repo.branch_to_commit:
        subgraph.node(branch, shape='parallelogram')
        subgraph.edge(branch, git_repo.branch_to_commit[branch][:6])

    print(graph.source)
    graph.render('git.gv', view=True)

  def get_display_name_for_blob(self, blob: Blob):
    return blob.name + ' ' + blob.hash[:6]

  def get_display_name_for_tree(self, tree: Tree):
    return tree.name + ' ' + tree.hash[:6]

def check_dependencies():
  if not shutil.which('dot'):
    print('Command "dot" was not found, please install graphviz first.')
    sys.exit(1)

def get_git_repo_path():
  if len(sys.argv) == 1:
    git_repo_path = os.getcwd()
  elif len(sys.argv) == 2:
    git_repo_path = sys.argv[1]
  else:
    print('Usage: {} [git-repo-path]'.format(os.path.basename(sys.argv[0])))
    sys.exit(1)
  dot_git_dir = os.path.join(git_repo_path, '.git')
  if not os.path.isdir(dot_git_dir):
    print('Invalid git repo path: {}'.format(git_repo_path))
    sys.exit(1)
  return git_repo_path

def parse_git_repo(dot_git_dir):
  git_repo = GitRepo(dot_git_dir)
  git_repo.parse_dot_git_dir()
  print('Branch to commit: {}'.format(git_repo.branch_to_commit))
  print('Commit to parents: {}'.format(git_repo.commit_to_parents))
  print('Commit to tree: {}'.format(git_repo.commit_to_tree))
  print('Tree to subtrees: {}'.format(git_repo.tree_to_trees))
  print('Tree to blobs: {}'.format(git_repo.tree_to_blobs))
  print('Blobs: {}'.format(git_repo.blobs))
  return git_repo

def generate_graph(git_repo):
  GraphGenerator().generate_graph(git_repo)

def main():
  check_dependencies()
  git_repo_path = get_git_repo_path()
  git_repo = parse_git_repo(git_repo_path)
  generate_graph(git_repo)


if __name__ == '__main__':
  main()
