import csv

from qscript import CaptureVideo_Magento

def main():
    with open('input.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=";", quotechar='"')
        for row in reader:
            video_path = CaptureVideo_Magento(
                url=row['URL'],
                company_name=row['Company Name'],
                language=row['Language'],
                country=row['Country'],
                postcode=row['Postcode'],
                city=row['City'],
                street=row['Street'],
                house_no=row['HouseNo']
            )
            if video_path:
                print(f"Saved: {video_path}")

if __name__ == "__main__":
    main()