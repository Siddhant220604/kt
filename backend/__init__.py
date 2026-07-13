from pathlib import Path

from dotenv import load_dotenv

package_dir = Path(__file__).resolve().parent
load_dotenv(package_dir / '.env')
load_dotenv(package_dir.parent / '.env')
