# -*- coding: utf-8 -*-
from django import forms
from django.conf import settings
from django.core.urlresolvers import reverse
from django.core import exceptions
from django.http import (HttpResponse, HttpResponseRedirect,
                         HttpResponseForbidden, Http404)
from django.shortcuts import render, redirect

from textbook.models import Page
from lessons.models import Stage, World
from lessons.models import QuizAnswer, QuizChallengeResponse
from students.models import Student

import random


# This handles the error handling and getting the proper module and lesson
# from the shortnames.
def get_stage(world, stage):
    try:
        world = World.objects.get(shortname=world)
        stage = Stage.objects.get(world=world, shortname=stage)
        return stage
    except exceptions.ObjectDoesNotExist: raise Http404()


# This displays the world map.
# TODO Trying to figure out how to specify between text mode and graphical mode.
def world_map(request, world):
    try: student = Student.from_request(request)
    except exceptions.ObjectDoesNotExist: return HttpResponse("Redirect to login")
    
    try: world = World.objects.get(shortname=world)
    except exceptions.ObjectDoesNotExist: raise Http404()
    
    # Here, we go through all of the stages and find out which ones we can see,
    # which one we can load, and which ones we've completed.
    stages = [] 
    completed = student.stage_set.all()
    for s in world.stage_set.all():
        available = True
        for p in s.prereqs.all():
            if p not in completed:
                available = False
        if available or (not s.hidden):
            stages.append( ( s, available, s in completed ) )
    
    return render( request, 'lessons_map.html', {'world': world,
                                                 'stage_list': stages} )


# This loads the stage based on whether the logged in user is in the "challenge
# first" or "lesson first" group.
def view_stage(request, world, stage):
    try: student = Student.from_request(request)
    except exceptions.ObjectDoesNotExist: return HttpResponse("Redirect to login")
    
    here = get_stage(world, stage)
    go = "lesson"
    # if in challenge-first group: go = "challenge"
    
    # If there is only one choice, then go to that one.
    if not here.lesson and here.challenge: go = "challenge"
    if not here.challenge and here.lesson: go = "lesson"
    return redirect( go, world = world, stage = stage )
    

# We load the lesson which shows the tutorial page in the left column and the
# chat stream (or other social tools) on the right. If no tutorial page exists,
# then we redirect to the challenge.
def view_lesson(request, world, stage):
    try: student = Student.from_request(request)
    except exceptions.ObjectDoesNotExist: return HttpResponse("Redirect to login")
    
    here = get_stage(world, stage)
    if not here.lesson:
        if here.challenge: return redirect( "challenge", world = world, stage = stage )
        else: raise Http404()
        
    #TODO log this as read.
    return render( request, "lessons_lesson.html", {'world': here.world,
                                                    'stage': here } )


# We load the challenge which looks different depending on which challenge
# family we're dealing with (hard-coded).
def view_challenge(request, world, stage):
    try: student = Student.from_request(request)
    except exceptions.ObjectDoesNotExist: return HttpResponse("Redirect to login")
    
    here = get_stage(world, stage)
    if not here.challenge:
        if here.lesson: return redirect( "lesson", world = world, stage = stage )
        else: raise Http404()
    
    # TODO log the view
    
    # These are all of the types of challenges.
    c = here.challenge
    if hasattr(c, "quizchallenge"): return view_quizchallenge(request,
                                                              world,
                                                              stage,
                                                              c.quizchallenge)
    raise Http404()


# This is a quizchallenge. This is pretty tricky to do since we have to be able
# to randomize the quizzes for the user without revealing any of the internal
# structure. To do so, we keep all of the models in the session parameter
# so we can map between the users choices to what they 'really are'.
def view_quizchallenge( request, world, stage, challenge ):
    here = get_stage(world, stage)
    if request.method == 'POST':
        return do_quizchallenge(request, world, stage, challenge)
        return redirect("challenge", world = world, stage = stage)
    
    # Questions is a list of tuples containing
    # (question, multi-choice?, [choiceA, choiceB...])
    answer_map = {}
    question_map = {}
    i = 0
    for q in challenge.questions.order_by('ordering'):
        choice_map = {}
        choice_map["a"] = q.choiceA
        choice_map["b"] = q.choiceB
        choice_map["c"] = q.choiceC
        choice_map["d"] = q.choiceD
        choice_map["e"] = q.choiceE
        
        # Here we add our choices and (optionally) shuffle them.
        choices = []
        if choice_map["a"]: choices.append("a")
        if choice_map["b"]: choices.append("b")
        if choice_map["c"]: choices.append("c")
        if choice_map["d"]: choices.append("d")
        if choice_map["e"]: choices.append("e")
        if q.random_ok: random.shuffle(choices)
        choice_content = []
        choice_letters = ["a","b","c","d","e"]
        for c in choices:
            choice_content.append( (choice_letters.pop(0), choice_map[c]) )
        
        # Here we map the displayed choices (keys) to the actual database
        # choices (value).
        choices += ["","","","",""]
        choice_map["a"] = choices[0]
        choice_map["b"] = choices[1]
        choice_map["c"] = choices[2]
        choice_map["d"] = choices[3]
        choice_map["e"] = choices[4]
        
        # Save this in the answer map and increment the counter.
        answer_map[i] = (q, choice_map)
        question_map[i] = (q.question, i, q.multiple_ok, choice_content)
        i += 1
        
    # Now the answer_map has been built, we decide whether or not we shuffle it.
    answers = list(range(len(answer_map)))
    if challenge.randomize: random.shuffle(answers)
    
    # We create our questions list and pass them on to the user.
    questions = []
    for a in answers:
        questions.append( question_map[a] )
    
    # Store the answer_map in a session parameter. The session parameter will
    # be passed back with the quiz so that we can 
    quizID = "quiz%d"%random.randint(1,1000000)
    request.session[quizID] = challenge, answer_map

    # Phew! Now render that bad boy!
    return render( request, "lessons_quiz_challenge.html",
                   {'questions': questions,
                    'world': here.world,
                    'stage': here,
                    'quizID': quizID } )


# This processes the quizchallenge and creates a QuizChallengeResponse for the
# user. The request.POST here should contain the "quizID" (which should be a
# session parameter), it should contain "q<N>" where N is the number of
# questions with values "A-E". We create a QuizAnswer for each question
# in the list, and then create a QuizChallengeResponse to hold them all.
def do_quizchallenge( request, world, stage, challenge ):
    here = get_stage(world, stage)
    if not here.challenge:
        if here.tutorial: return redirect( "lesson", world = world, stage =stage )
        else: raise Http404()
    quizID = request.POST.get("quizID")
    challenge, answer_map = request.session.get(quizID)
    
    if challenge is None or answer_map is None: pass # raise shenanigans.
    
    # First we extract all of the responses from the form.
    responses = []
    q = 0
    while "q%d"%q in request.POST:
        responses.append( request.POST.getlist("q%d"%q) )
        q += 1
    
    # For each of the questions, we create a QuizAnswer and store it in the
    # answers list. Assuming we get all the way through without any shenanigans,
    # we'll save all of those models, then create a single QuizChallengeResponse
    # to hold them.
    answers = []
    score = 0
    total = 0
    for q in range(len(responses)):
        if q not in answer_map: pass # raise shenanigans.
        total += 1
        QA = QuizAnswer()
        raw_response_list = responses[q]
        QA.question, choice_map = answer_map[q]
        response_list = []
        for r in raw_response_list:
            if r in answer_map: response_list.append( answer_map[r] )
        if 'A' in response_list: QA.selectedA = True
        if 'B' in response_list: QA.selectedB = True
        if 'C' in response_list: QA.selectedC = True
        if 'D' in response_list: QA.selectedD = True
        if 'E' in response_list: QA.selectedE = True
        
        ans = True
        if QA.question.multiple_ok:
            if QA.selectedA != QA.question.correctA: ans = False
            if QA.selectedB != QA.question.correctB: ans = False
            if QA.selectedC != QA.question.correctC: ans = False
            if QA.selectedD != QA.question.correctD: ans = False
            if QA.selectedE != QA.question.correctE: ans = False
        else:
            ans = False
            if QA.selectedA == QA.question.correctA: ans = True
            if QA.selectedB == QA.question.correctB: ans = True
            if QA.selectedC == QA.question.correctC: ans = True
            if QA.selectedD == QA.question.correctD: ans = True
            if QA.selectedE == QA.question.correctE: ans = True
        if ans: score += 1
        QA.correct = ans
        
        answers.append(QA)
    
    # We made it through safely! Now we save the response in the DB.
    for QA in answers: QA.save()
    QCR = QuizChallengeResponse()
    QCR.quiz = challenge
    QCR.student = request.user.student
    QCR.score = score
    QCR.correct = (score == total)
    QCR.save()  # Can't do many-to-many until we save it once.
    for QA in answers: QCR.answers.add(QA)
    QCR.save()
    
    # If QCR was correct, add the stage to the Student's completion record.
    
    return HttpResponse( str(responses) )

