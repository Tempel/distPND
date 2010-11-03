from distutils.core import Command
from distutils.errors import DistutilsOptionError, DistutilsFileError
from .gen_pxml import gen_pxml
import shutil, os.path
import subprocess as sp

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
		self.build_dir = 'build_pnd' #This doesn't get used yet until I can figure out how to finagle the install command.
		self.clean = False

	
	def finalize_options(self):
		if self.format not in ('squashfs', 'isofs', 'none', 'auto'):
			raise DistutilsOptionError("%s is not a valid package format.  Use squashfs, isofs, none, or auto"%self.format)
		
		if (self.pxml is not None) and (not os.path.exists(self.pxml)):
			raise DistutilsFileError('PXML file %s does not exist'%self.pxml)

		if self.pndname is None:
			if self.pxml is None:
				self.pndname = self.distribution.get_name().replace(' ','-') + '.pnd'
			else: pass
				#read pxml file to get appdata/id

		#Arguments to calls taken from official pnd_make.sh.
		self.squashfs_call = ('mksquashfs', self.build_dir, self.pndname, '-nopad', '-no-recovery', '-noappend')
		self.isofs_call = ('mkisofs', '-o%s'%self.pndname, self.build_dir)
		print self.isofs_call
	
	
	def run(self):
		if self.clean:
			shutil.rmtree(self.build_dir)

		self.run_command('install')
		#specify root=build_dir, all install-*=/

		if self.pxml is None:
			self.run_command('gen_pxml')
			#specify to install to build_dir/PXML.xml, somehow
		else:
			shutil.copy(self.pxml, os.path.join(self.build_dir, 'PXML.xml'))
		
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
		pxml = open(os.path.join(self.build_dir, 'PXML.xml'), 'rb')
		try:
			pnd.write(pxml.read())
			#Scan pxml for icon, and append that too.
		finally: pnd.close()
