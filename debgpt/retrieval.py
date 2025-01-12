'''
Copyright (C) 2024-2025 Mo Zhou <lumin@debian.org>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
'''
from typing import List
import sys
import argparse
import numpy as np
from rich.status import Status
from . import defaults
from . import vectordb
from . import embeddings

console = defaults.console


class AbstrastRetriever(object):  # pragma: no cover
    '''
    Abstract class for retrievers.
    '''

    def __init__(self, args: object):
        pass

    def retrieve_onfly(self,
                       query: str,
                       documents: List[str],
                       topk: int = 3) -> List[str]:
        pass

    def add(self, source: str, text: str) -> np.ndarray:
        pass

    def retrieve_from_db(self, query: str, topk: int = 3) -> List[str]:
        pass


class VectorRetriever(object):
    '''
    Vector-based retriever.
    '''

    def __init__(self, args: object):
        self.vdb = vectordb.VectorDB(args.db, args.embedding_dim)
        self.model = embeddings.get_embedding_model(args)

    def retrieve_onfly(self,
                       query: str,
                       documents: List[str],
                       topk: int = 3) -> List[str]:
        '''
        This function retrieves the top-k most relevant documents from the
        document list given a query. It does not modify the database, nor
        query the database. It computes the embeddings on-the-fly.

        Args:
            query: the query string.
            documents: a list of document strings.
            topk: the number of documents to retrieve.
        Returns:
            a list of top-k most relevant documents.
        '''
        query_embedding = self.model.embed(query)
        document_embeddings = self.model.batch_embed(documents)
        cosine = np.dot(document_embeddings, query_embedding)
        indices = np.argsort(cosine)[::-1][:topk]
        results = []
        for sim, doc in zip(cosine[indices], [documents[i] for i in indices]):
            doc = [float(sim), '<temporary>', doc]
            results.append(doc)
        return results

    def add(self, source: str, text: str) -> np.ndarray:
        '''
        This function computes and adds a new vector to the database.

        Args:
            source: the source of the text.
            text: the text to be added.
        Returns:
            the computed vector.
        '''
        with Status('computing embedding ...', console=console):
            vector = self.model.embed(text)
        self.vdb.add(source, text, vector)
        return vector

    def batch_add(self, sources: List[str],
                  texts: List[str]) -> List[np.ndarray]:
        '''
        This function computes and adds a batch of new vectors to the database.

        Args:
            sources: a list of sources of the texts.
            texts: a list of texts to be added.
        Returns:
            a list of computed vectors.
        '''
        with Status('computing embedding ...', console=console):
            vectors = self.model.batch_embed(texts)
        for source, text, vector in zip(sources, texts, vectors):
            self.vdb.add(source, text, vector)
        return vectors

    def retrieve_from_db(self, query: str, topk: int = 3) -> List[str]:
        '''
        This function retrieves the top-k most relevant documents from the
        database given a query.

        Args:
            query: the query string.
            topk: the number of documents to retrieve.
        Returns:
            a list of top-k most relevant documents.
        '''
        query_embedding = self.model.embed(query)
        documents = self.vdb.retrieve(query_embedding, topk)
        return documents


def main(argv):
    # argument parser
    parser = argparse.ArgumentParser(description='retrieval')
    parser.add_argument('--db',
                        type=str,
                        default='test.db',
                        help='database file')
    parser.add_argument('--embedding_frontend',
                        '-E',
                        type=str,
                        default='openai',
                        choices=['openai', 'google', 'random'],
                        help='embedding frontend')
    subparsers = parser.add_subparsers(dest='subcommand')

    # subcommand: add
    parser_add = subparsers.add_parser('add')
    parser_add.add_argument('-s',
                            type=str,
                            default='',
                            help='source of this text')
    parser_add.add_argument('text', type=str, help='text to be added')
    # subcommand: retrieve
    parser_retrieve = subparsers.add_parser('retrieve', aliases=['ret'])
    parser_retrieve.add_argument('query', type=str, help='query string')
    parser_retrieve.add_argument('-k',
                                 type=int,
                                 default=3,
                                 help='number of documents to retrieve')
    # parse arguments and create configuration
    args = parser.parse_args(argv)
    conf = defaults.Config()
    conf.db = args.db
    conf.embedding_frontend = args.embedding_frontend
    retriever = VectorRetriever(conf)

    if args.subcommand == 'add':
        vector = retriever.add(args.s, args.text)
        print('vector added:', vector.shape)
    elif args.subcommand in ('retrieve', 'ret'):
        documents = retriever.retrieve_from_db(args.query, args.k)
        for doc in documents:
            print(doc)


if __name__ == '__main__':  # pragma: no cover
    main(sys.argv[1:])
