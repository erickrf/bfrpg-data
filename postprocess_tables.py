import argparse
import json

# some replacements for matching all keys
stat_name_replacements = {
    'Treasure': 'Treasure Type',
    'Movements': 'Movement',
    'Save as': 'Save As',
    'No of Attacks': 'No. of Attacks',
    'No. of Attack': 'No. of Attacks',
    'No Appearing': 'No. Appearing',
    'Attacks': 'No. of Attacks',
    'Armour Class': 'Armor Class',
    'XP value': 'XP',
    'XP Value': 'XP'
}

class Processor:
    def __init__(self, expected_stats=None):
        self.multitable = 0
        self.expected_stats = expected_stats

    def extract_stats(self, item: dict, name: str):
        tables = item['tables']

        if len(tables) > 1:
            self.multitable += 1
            print(f'{name} has multiple tables')

        rows = tables[0]['rows']
        stats = []
        values = []
        try:
            for stat, value in rows:
                # special treatment to some noisy cases like "Save As: Figher:"
                if stat.startswith('Save') and stat.count(':') == 2:
                    stat, save_class = stat.split(':', 1)

                    # fix value to "Fighter: xx"
                    value = save_class + value

                stat = stat.strip(': ')
                stat = stat_name_replacements.get(stat, stat)

                stats.append(stat)
                values.append(value)

        except ValueError:
            print(f'Unexpected data in {name}: {rows}')
            return [], []

        return stats, values

    def process_file(self, filename: str):
        """
        Process one file
        """
        with open(filename) as f:
            data = json.load(f)

        result = {}

        for monster, monster_data in data.items():
            stats, values = self.extract_stats(monster_data, monster)
            stats = set(stats)

            if self.expected_stats is None:
                self.expected_stats = set(stats)
            else:
                missing = self.expected_stats - stats
                additional = stats - self.expected_stats

                if missing:
                    print(f'{monster} is missing {missing}')

                if additional:
                    print(f'{monster} has additional stats: {additional}')

            result[monster] = {s: v for s, v in zip(stats, values)}

        return result


def main():
    parser = argparse.ArgumentParser(description="Postprocess tables data")
    parser.add_argument("input_file", help="Input JSON file")
    parser.add_argument("output_file", help="Output JSON file")
    args = parser.parse_args()


if __name__ == '__main__':
    main()
