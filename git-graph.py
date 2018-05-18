#!/usr/bin/env python3.5

import collections
import os
import subprocess

from typing import Dict, Tuple, List

# Git object types.
Branch = collections.namedtuple('Branch', 'name commit')
Commit = collections.namedtuple('Commit', 'tree parent author committer')
Hash = str

git_dir = os.path.join(os.getcwd(), '.git')

# object cache: hash -> object (commit, tree, blob).
cache = {}

# Lists all the branches of the git repo.
def list_branches() -> List[Branch]:
  heads_dir = os.path.join(git_dir, 'refs', 'heads')
  files = os.listdir(heads_dir)
  return [Branch(name=f, commit=read_txt(os.path.join(heads_dir, f))) for f in files]

# Traverses the history of a branch.
def traverse_history(branch: Branch):
    head_commit = get_commit(branch.commit)
    print(head_commit)

# Gets the commit for a hash.
def get_commit(hash: Hash) -> Commit:
  if hash not in cache:
    content = git_cat_file(hash)
    cache[hash] = parse_commit(content)
  return cache[hash]

def parse_commit(content: str) -> Commit:
  lines = content.split('\n')
  dict = {}
  for line in lines:
    if not line:
      break
    parts = line.split(' ')
    dict[parts[0]] = ' '.join(parts[1:])
  print(dict)
  return Commit(**dict)

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

def main():
  branches = list_branches()
  print('Branches: {}'.format(branches))
  for branch in branches:
    traverse_history(branch)


if __name__ == '__main__':
  main()
