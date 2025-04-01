from rapidfuzz import fuzz
import pandas as pd
import numpy as np
import re
from tqdm.auto import tqdm
tqdm.pandas()


def norm_string(s):
    """Remove punctuation and lowercase"""
    return re.sub(r'[^a-zA-Z0-9\s]', '', str(s).lower().strip())


class CompanyMap:
    def __init__(self, df, name_cols, addr_col):
        self.df = df.copy()
        self.name_cols = name_cols
        self.addr_col = addr_col
        self.ref_name = "ref"
        self.learned_data = self._prepare_data()

    def _prepare_data(self):
        df = self.df.copy()
        for col in self.name_cols + [self.addr_col]:
            df[col] = df[col].fillna("").apply(norm_string)
        return df

    def get_match_idx(self, name_series, address, threshold=95, avg_threshold=80):
        name_series = name_series.fillna("").apply(norm_string)
        address = norm_string(address)
        matches = []

        for i, row in self.learned_data.iterrows():
            name_scores = [fuzz.partial_ratio(name_series[col], row[col]) for col in self.name_cols]
            addr_score = fuzz.partial_ratio(address, row[self.addr_col])
            max_name = max(name_scores)
            avg_score = (max_name + addr_score) / 2

            if avg_score >= avg_threshold or max_name >= threshold or addr_score >= threshold:
                matches.append(i)

        return matches


class OneMapToRuleThemAll(CompanyMap):
    def __init__(self, mappers, threshold=95, avg_threshold=80):
        self.mappers = {m.ref_name: m for m in mappers}
        self.threshold = threshold
        self.avg_threshold = avg_threshold

        df, names, addr = self._concat_data()
        super().__init__(df, names, addr)
        self.learned_data['internal_match'] = self._internal_matches(self.learned_data)

    def _concat_data(self):
        frames = []
        for k, m in self.mappers.items():
            frame = m.learned_data[m.name_cols + [m.addr_col]].copy()
            frame['keys'] = list(zip([k] * len(frame), m.learned_data.index))
            frames.append(frame)

        df = pd.concat(frames)
        names = self.name_cols
        addr = self.addr_col
        df = df.groupby(names + [addr]).agg({'keys': list}).reset_index()
        return df, names, addr

    def _internal_matches(self, df):
        return df.progress_apply(
            lambda x: self.get_match_idx(
                x[self.name_cols],
                x[self.addr_col],
                self.threshold,
                self.avg_threshold
            ), axis=1
        )

    def get_matches(self, names=[], address='', threshold=95, avg_threshold=80):
        df = self.get_match_df(names, address, threshold, avg_threshold, fuzzy_alg=fuzz.partial_ratio)
        matches = self.get_match_df(names, address, threshold, avg_threshold, fuzzy_alg=fuzz.partial_ratio)['internal_match']
        results = {}
        for map_id, idx in pd.DataFrame((self.learned_data.iloc[matches.values.sum()]['keys'].values).sum()).groupby(0):
            results[map_id] = self.mappers[map_id].learned_data.iloc[idx[1].values]
        return results


# Simple wrapper for basic fuzzy join use case
def fuzzy_join(left_df, right_df, left_name_cols=['signatory_name'], right_name_cols=['company_name'],
               left_addr_col='signatory_address', right_addr_col='zip_cd', how='inner', threshold=95, avg_threshold=80):

    c = CompanyMap(right_df, right_name_cols, right_addr_col)
    matches = left_df.progress_apply(
        lambda x: c.get_match_idx(x[left_name_cols], x[left_addr_col], threshold, avg_threshold), axis=1)
    df = pd.concat([left_df, pd.DataFrame(matches.tolist())], axis=1).melt(id_vars=left_df.columns)
    df = df.set_index('value', drop=False).join(c.learned_data, lsuffix='_l', rsuffix='_r', how=how)
    return df
