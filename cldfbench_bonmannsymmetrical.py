import pathlib
import re
import sys
from collections import defaultdict

from cldfbench import Dataset as BaseDataset, CLDFSpec

from pybtex.database import parse_string


def make_examples(csv_examples):
    examples = defaultdict(list)
    # TODO: sources
    for ex in csv_examples:
        glottocode = ex['Glottocode']
        analyzed = [w.strip() for w in ex['Primary text'].split('\t')]
        gloss = [w.strip() for w in ex['Gloss'].split('\t')]
        translation = ex['Translation']
        if not analyzed or not translation:
            continue
        examples[glottocode].append({
            'Language_ID': glottocode,
            'Primary_Text': ' '.join(analyzed),
            'Analyzed_Word': analyzed,
            'Gloss': gloss,
            'Translated_Text': translation,
            'Source_comment': ex['Source'],
        })

    for glottocode, language_examples in examples.items():
        for nr, example in enumerate(language_examples, 1):
            example['ID'] = f'{glottocode}-{nr}'

    return examples


def make_languages(raw_table, glottolog):
    language_names = {
        row['Glottolog Code']: row['Language'] for row in raw_table}
    languoids = {
        lg.id: lg for lg in glottolog.languoids(ids=language_names)}
    return [
        {'ID': glottocode,
         'Glottocode': glottocode,
         'Name': name,
         'ISO639P3code': (lg := languoids[glottocode]).iso,
         'Latitude': lg.latitude,
         'Longitude': lg.longitude,
         'Macroarea': lg.macroareas[0] if lg.macroareas else ''}
        for glottocode, name in language_names.items()]


def valid_source(source_string, bibentries):
    bibkey, _ = re.fullmatch('(.*?)(\[[^\]]*\])?', source_string).groups()
    if bibkey in bibentries:
        return True
    else:
        print('unkown source:', source_string, file=sys.stderr)
        return False


def make_value(row, code, examples_by_gc, bibentries):
    glottocode = row['Glottolog Code']
    source_strings = re.split(r'\s*;\s*', row['Sources'])
    perscomm = [
        s
        for s in source_strings
        if 'personal communication' in s
        or 'field notes' in s]
    bibentries = [
        s
        for s in source_strings
        if s not in perscomm
        and valid_source(s, bibentries)]
    examples = [
        ex['ID']
        for ex in examples_by_gc.get(glottocode, ())]
    return {
        'ID': f'{glottocode}-dom',
        'Language_ID': glottocode,
        'Parameter_ID': 'dom',
        'Example_IDs': examples,
        'Code_ID': code['ID'],
        'Value': code['Name'],
        'Source': bibentries,
        'Source_comment': '; '.join(perscomm),
    }


def make_values(raw_table, parameters, codes, examples_by_gc, bibentries):
    return [
        make_value(row, codes[row['DOM Classification']], examples_by_gc, bibentries)
        for row in raw_table]


def make_schema(cldf):
    cldf.add_columns(
        'ValueTable',
        {'name': 'Example_IDs',
         'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#exampleReference',
         'datatype': 'string',
         'separator': ';',
         'dc:extent': 'multivalued'},
        'Source_comment')

    cldf.add_component('LanguageTable')
    cldf.add_component('ParameterTable')
    cldf.add_component('CodeTable', 'Map_Icon')
    cldf.add_component(
        'ExampleTable',
        {'name': 'Source',
         'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#source',
         'separator': ';',
         'dc:extent': 'multivalued'},
        'Source_comment')

    cldf.add_foreign_key(
        'ValueTable', 'Example_IDs',
        'ExampleTable', 'ID')


class Dataset(BaseDataset):
    dir = pathlib.Path(__file__).parent
    id = "bonmannsymmetrical"

    def cldf_specs(self):  # A dataset must declare all CLDF sets it creates.
        return CLDFSpec(
            module='StructureDataset',
            dir=self.cldf_dir,
            metadata_fname='cldf-metadata.json')

    def cmd_download(self, args):
        """
        Download files to the raw/ directory. You can use helpers methods of `self.raw_dir`, e.g.

        >>> self.raw_dir.download(url, fname)
        """

    def cmd_readme(self, args):
        section_header = (
            'Differential object marking in symmetrical voice languages\n'
            '==========================================================\n'
            '\n')
        section_content = self.raw_dir.read('intro.md')
        return f'{section_header}\n{section_content}'

    def cmd_makecldf(self, args):
        """
        Convert the raw data to a CLDF dataset.

        >>> args.writer.objects['LanguageTable'].append(...)
        """
        raw_table = [
            {k: trimmed for k, v in row.items() if (trimmed := v.strip())}
            for row in self.raw_dir.read_csv('bonmannsymmetrical.csv', dicts=True)]

        examples_by_gc = make_examples(self.raw_dir.read_csv('examples.csv', dicts=True))

        parameters = {
            row['Original_Name']: row
            for row in self.etc_dir.read_csv('parameters.csv', dicts=True)}
        codes = {
            row['Original_Name']: row
            for row in self.etc_dir.read_csv('codes.csv', dicts=True)}
        sources = parse_string(self.raw_dir.read('sources.bib'), 'bibtex')

        languages = make_languages(raw_table, args.glottolog.api)
        values = make_values(
            raw_table, parameters, codes, examples_by_gc, sources.entries)

        # write cldf

        make_schema(args.writer.cldf)

        args.writer.objects['LanguageTable'] = languages
        args.writer.objects['ParameterTable'] = parameters.values()
        args.writer.objects['CodeTable'] = codes.values()
        args.writer.objects['ValueTable'] = values
        args.writer.objects['ExampleTable'] = [
            ex
            for exs in examples_by_gc.values()
            for ex in exs]

        args.writer.cldf.add_sources(sources)
