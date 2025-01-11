'''
Copyright (C) 2024 Mo Zhou <lumin@debian.org>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
'''

# From https://salsa.debian.org/nm-team/nm-templates
NM_TEMPLATES = {
        # https://salsa.debian.org/nm-team/nm-templates/-/blob/master/nm_pp1.txt?ref_type=heads
        'pp1.PH0': '''First, please have a careful read of the Social Contract and the DFSG. What do you think are their main points?''',
        'pp1.PH1': '''What is Debian's approach to non-free software? Why? Is non-free part of the Debian System? Please also explain the difference between non-free and the other sections.''',
        'pp1.PH2': '''Suppose that Debian were offered a Debian-specific license to package a certain piece of software: would we put it in main?''',
        'pp1.PH3': '''Please explain the difference between free as in "free speech" and as in "free beer". Is Debian mainly about free as in "free speech" or free as in "free beer"?''',
        'pp1.PH4': '''What is your opinion about how the DFSG should be applied to files that are not software, such as documentation, firmware, images, etc? Specifically, DFSG section 2 "Source Code".''',
        'pp1.PH5': '''How do you check if a license is DFSG-compatible? Who has the final say over what can be included in Debian?''',
        'pp1.PH6': '''There are a few "tests" for this purpose, based on (not really) common situations. Explain them to me and point out which common problems can be discovered by them.''',
        'pp1.PH7': '''At https://people.debian.org/~joerg/bad.licenses.tar.bz2 you can find a tarball of bad licenses. Please compare the graphviz and three other (your choice) licenses with the first nine points of the DFSG and show a few examples of where they do not comply with the DFSG. There's no need to compare word for word (which would be impossible for some licenses anyway), but you should spot the biggest mistakes.  Note: the graphviz license is bad for the brain: don't take too much of it.  Also note: graphviz and qmail have now changed licenses in favour of free ones.''',
        'pp1.PHa': '''Are there any sections of the DFSG or Social Contract that you might like to see changed? If so, which ones, and why?''',
}
