# -*- coding: utf-8 -*-
from django.db import models

from students.models import Student
from lessons.models import BaseChallenge


# Challenge type: Assembly Program
class AssemblyChallenge(BaseChallenge):
    kernal      = models.BooleanField("kernal", default=False,
                        help_text="The kernal for this challenge.")
                        
    def __unicode__(self):
        return u'AssemblyChallenge %d'%(self.id)


# The form submitted when an assembly challenge is attempted. These challenge
# responses contain the entire source code of every student submission.
# If the challenge variable is null, that means that the challenge was submitted
# on the playground.
# There's no reason to worry about saving the compiled ROMs, since those can
# be assembled on the fly (and it's safe, since we've got a two-pass assembler).
class AssemblyChallengeResponse(models.Model):
    challenge = models.ForeignKey(AssemblyChallenge, verbose_name="challenge",
                                  blank=True, null=True)
    student   = models.ForeignKey(Student, verbose_name="student", blank=True,
                                  null=True)
    code      = models.TextField("code", blank=True)
    timestamp = models.DateTimeField("timestamp", auto_now=True)
        
    def __unicode__(self):
        return u'AssemblyResponse %d from %s'%(self.id,self.student.username)


# The Kernal table stores assembly code to be invoked when ".include" is called.
class Kernal(models.Model):
    name = models.SlugField("name", unique=True)
    code = models.TextField("code")
    
    def __unicode__(self):
        return u'Kernal %s'%(self.name)


# The Pattern table stores binary data and adds it when ".incbin" is called.
# The data is actually stored in ASCII Hex (maybe upgrade to ASCII85 in the
# future).
class Pattern(models.Model):
    name = models.SlugField("name", unique=True)
    code = models.TextField("code")

    def __unicode__(self):
        return u'Pattern %s'%(self.name)

