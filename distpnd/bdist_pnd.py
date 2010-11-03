from distutils.core import Command, run_setup
from distutils.errors import DistutilsOptionError, DistutilsFileError
import shutil, os
import subprocess as sp
from xml.dom.minidom import parse

class bdist_pnd(Command):

	description = 'install everything to a PND file'

	user_options=[
		('format=', None,
		'specify which package format to use - squashfs, isofs, none, or auto'),
		('pxml=', None,
		'specify a PXML file to use (default uses gen_pxml to create one)'),
		('pndname=', None,
		'specify a name for the resulting PND file (default determines from PXML appdata/id)'),
		('build-dir=', None,
		'specify the directory in which to assemble the PND (default is build_pnd)'),
		('clean', None,
		'flag to automatically clean out the build-dir before installing'),
		#Could add pass-through options to gen_pxml.  For now, let them be done in setup.cfg.
		#Maybe some pass-through options to install?  Not yet.
	]
	
	
	def initialize_options(self):
		self.format = 'auto'
		self.pxml = None
		self.pndname = None
		self.build_dir = 'build_pnd'
		self.clean = False

	
	def finalize_options(self):
		if self.format not in ('squashfs', 'isofs', 'none', 'auto'):
			raise DistutilsOptionError("%s is not a valid package format.  Use squashfs, isofs, none, or auto"%self.format)
		
		if (self.pxml is not None) and (not os.path.exists(self.pxml)):
			raise DistutilsFileError('PXML file %s does not exist'%self.pxml)

		#If an output filename is not specified, come up with one.
		if self.pndname is None:
			if self.pxml is None:
				self.pndname = self.distribution.get_fullname() + '.pnd'
			else:
				#Parses PXML file, using appdata (or, if that doesn't exist, id).
				app = parse(self.pxml).getElementsByTagName('application')[0]
				self.pndname = app.getAttribute('appdata')
				if self.pndname == '':
					self.pndname = app.getAttribute('id')
				self.pndname += '.pnd'
		
		#As this creates a distribution, it should be in the dist folder
		#and should make itself available to the upload command.
		self.distribution.dist_files.append(('bdist_pnd', self.pndname))
		try: os.mkdir('dist')
		except OSError: pass
		self.pndname = os.path.join('dist', self.pndname)

		#Arguments to calls taken from official pnd_make.sh.
		self.squashfs_call = ('mksquashfs', self.build_dir, self.pndname, '-nopad', '-no-recovery', '-noappend')
		self.isofs_call = ('mkisofs', '-o%s'%self.pndname, self.build_dir)
	
	
	def run(self):
		if self.clean:
			shutil.rmtree(self.build_dir)

		#Runs "install" such that all files are put into self.build_dir.
		#Specifying / for all the install-* might not work cross-platform.
		run_setup(self.distribution.script_name, ('install', '--root=%s'%self.build_dir,
			'--install-lib=/', '--install-scripts=/', '--install-data=/'))

		#Generate a PXML in self.build_dir if needed.
		pxml_final = os.path.join(self.build_dir, 'PXML.xml')
		if self.pxml is None:
			run_setup(self.distribution.script_name, ('gen_pxml', '--force',
				'--outfile=%s'%pxml_final))
		else:
			shutil.copy(self.pxml, pxml_final)

		#If icon or info are in PXML, warn if they didn't make it into the PND.
		try: icon = parse(pxml_final).getElementsByTagName('icon')[0].getAttribute('src')
		except IndexError: icon = ''
		if icon != '' and (not os.path.exists(os.path.join(self.build_dir, icon))):
			self.warn('Specified icon file has not been found in your PND.  You have to make sure it gets installed somehow.  Your PND will have no icon.')
			icon = ''

		try: info = parse(pxml_final).getElementsByTagName('info')[0].getAttribute('src')
		except IndexError: info = ''
		if info != '' and (not os.path.exists(os.path.join(self.build_dir, info))):
			self.warn('Specified info file has not been found in your PND.  You have to make sure it gets installed somehow.  Attempting to open your help file will fail.')
		
		#Make initial fs file.
		if self.format == 'auto':
			#Try squash, then warn, then iso, then warn, then just copy directory.
			try: sp.call(self.squashfs_call)
			except OSError:
				self.warn('mksquashfs not found.  Trying mkisofs.')
				try: sp.call(self.mkisofs_call)
				except OSError:
					self.warn('mkisofs not found.  Copying %s to %s'%(self.build_dir, self.pndname))
					shutil.copytree(self.build_dir, self.pndname)
					return #Since we can't append anything to a directory, we're done.
		elif self.format == 'squashfs':
			sp.call(self.squashfs_call)
		elif self.format == 'isofs':
			sp.call(self.isofs_call)
		else:
			shutil.copytree(self.build_dir, self.pndname)
			return #Since we can't append anything to a directory, we're done.
		
		#Then append PXML and icon.
		pnd = open(self.pndname, 'ab')
		pxml = open(pxml_final, 'rb')
		try:
			pnd.write(pxml.read())
			if icon != '':
				icon = open(os.path.join(self.build_dir, icon), 'rb')
				pnd.write(icon.read())
				icon.close()
		finally:
			pnd.close()
			pxml.close()
