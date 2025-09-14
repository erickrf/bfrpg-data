import argparse
import json

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
        try:
            stats, values = zip(*rows)
        except ValueError:
            print(f'Unexpected data in {name}: {rows}')
            return [], []

        stats = [stat.strip(':') for stat in stats]

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
