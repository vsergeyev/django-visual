# Visual Django

Visual IDE designed in Python 3.x to work with projects based on Django framework (https://www.djangoproject.com)

Inspired by Borland Delphi (long live the king!).

## IDE

IDE offers capabilities and visual tools for:

 * New Project Templates
   * Empty project
   * Blog project
   * Content Web Site
   * 1-Page Application

 * Project Navigator
   * Django Project properties (settings)
   * Applications editor
   * URLs designer

 * Models Designer
   * App -> Models View & Edit
   * Human UI for Model fields with help

 * View -> Template Visual Editor
   * like TForm in Delphi
   * Queries editor for view
   * Output variables (what View returns)
   * Template visual editor (inputs, sections - header, detail, list, footer)

 * Database Viewer

 * Package Visual Django as an executable with PyInstaller
 https://github.com/pyinstaller/pyinstaller/wiki/Recipe-Executable-From-Django


## Hints

 * Explore project files in Project Navigator
 * Look on project's Applications
 * Database by default is SQLITE3
 * Run project with green button

## Development setup

First please create a virtual environment:

    virtualenv venv -p python3

Activate it with command:

    source ./venv/bin/activate

Now let install requred packages, not so much actually:

    pip install -r requirements.txt

Known issues:

 * 'psycopg2' package installation may result in error. You may use 'psycopg2-binary' pre-built package as well
 * it may require to install postgresql to fix 'psycopg2' error


## Have a question?

 * Email me: vova.sergeyev@gmail.com
 * Create issue on Github https://github.com/vsergeyev/django-visual/issues

## Thank you!
