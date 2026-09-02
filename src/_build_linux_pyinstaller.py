from glob import glob
import os
import PyInstaller.__main__
import shutil
import sys

if 'linux' not in sys.platform:
    print("this script is for linux only!")
    exit()

def clean(additional=None):
	removethese = ['__pycache__','build','dist','*.spec']
	if additional:
		removethese.extend(additional)
	for _object in removethese:
		target=glob(os.path.join('.', _object))
		for _target in target:
			try:
				if os.path.isdir(_target):
					shutil.rmtree(_target)
				else:
					os.remove(_target)
			except:
				print(f'Error deleting {_target}.')

THIS_VERSION = None
try:
	mainfile = open('duckypad_config.py')
	for line in mainfile:
		if "THIS_VERSION_NUMBER =" in line:
			THIS_VERSION = line.replace('\n', '').replace('\r', '').split("'")[-2]
	mainfile.close()
except Exception as e:
	print('build_linux exception:', e)
	exit()

if THIS_VERSION is None:
	print('could not find version number!')
	exit()

exe_file_name = f"duckypad_config_{THIS_VERSION.replace('.', '_')}_linux_x86_64"

# --noconsole
# (the output folder name is passed as additional so re-runs never hit a
# stale directory at the os.rename step)
clean(additional=['duckypad*.zip', exe_file_name])

# uv-managed CPython builds (e.g. ~/.local/share/uv/python/...) bundle
# Tcl/Tk 9 inside their own lib dir, which is NOT on the dynamic loader's
# search path, so PyInstaller can't resolve libtcl*/libtk* from _tkinter.
# Bundle the shared objects when found there so the frozen app runs
# standalone; on a standard distro install the system Tcl/Tk resolves
# normally and this adds nothing.
pylib = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(sys.executable))), 'lib')
tcl_addbin = []
for _lib in ('libtcl9.0.so', 'libtcl9tk9.0.so'):
	_p = os.path.join(pylib, _lib)
	if os.path.exists(_p):
		tcl_addbin.append(f'--add-binary={_p}:.')

PyInstaller.__main__.run([
	'duckypad_config.py',
	'--collect-all=certifi',
	'--onefile',
	f'--name={exe_file_name}'
] + tcl_addbin)

output_folder_path = os.path.join(".", "dist")
new_folder_path = exe_file_name

print(output_folder_path)
print(new_folder_path)

os.rename(output_folder_path, new_folder_path)

readme_content = """

Launching this app on Linux:

https://dekunukem.github.io/duckyPad-Pro/doc/linux_macos_notes.html

Full User Manuals:

duckyPad.com

"""

with open(os.path.join(new_folder_path, "README.txt"), "w") as f:
	f.write(readme_content)

zip_file_name = exe_file_name
shutil.make_archive(exe_file_name, 'zip', new_folder_path)

clean()
