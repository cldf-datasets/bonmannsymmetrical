import pathlib
import re
import sys

from cldfbench import Dataset as BaseDataset, CLDFSpec

from pybtex.database import parse_string


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


def make_value(row, code, bibentries):
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
    return {
        'ID': f'{glottocode}-dom',
        'Language_ID': glottocode,
        'Parameter_ID': 'dom',
        'Code_ID': code['ID'],
        'Value': code['Name'],
        'Source': bibentries,
        'Source_comment': '; '.join(perscomm),
    }


def make_values(raw_table, parameters, codes, bibentries):
    return [
        make_value(row, codes[row['DOM Classification']], bibentries)
        for row in raw_table]


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

    def cmd_makecldf(self, args):
        """
        Convert the raw data to a CLDF dataset.

        >>> args.writer.objects['LanguageTable'].append(...)
        """
        raw_table = [
            {k: trimmed for k, v in row.items() if (trimmed := v.strip())}
            for row in self.raw_dir.read_csv('bonmannsymmetrical.csv', dicts=True)]
        parameters = {
            row['Original_Name']: row
            for row in self.etc_dir.read_csv('parameters.csv', dicts=True)}
        codes = {
            row['Original_Name']: row
            for row in self.etc_dir.read_csv('codes.csv', dicts=True)}
        sources = parse_string(self.raw_dir.read('sources.bib'), 'bibtex')

        languages = make_languages(raw_table, args.glottolog.api)
        values = make_values(raw_table, parameters, codes, sources.entries)

        # write cldf

        args.writer.cldf.add_columns('ValueTable', 'Source_comment')
        args.writer.cldf.add_component('LanguageTable')
        args.writer.cldf.add_component('ParameterTable')
        args.writer.cldf.add_component('CodeTable', 'Map_Icon')

        args.writer.objects['LanguageTable'] = languages
        args.writer.objects['ParameterTable'] = parameters.values()
        args.writer.objects['CodeTable'] = codes.values()
        args.writer.objects['ValueTable'] = values

        args.writer.cldf.add_sources(sources)
