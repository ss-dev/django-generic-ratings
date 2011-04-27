from django.db.models.base import ModelBase

from ratings import settings, models, forms, exceptions

class RatingHandler(object):
    """
    Encapsulates content rating options for a given model.
    
    This class can be subclassed to specify different behaviour and options
    for ratings of a given model, but can also be used directly, just to
    handle default rating for any model. 
    
    The default rating provide only one 0-10 ranged (without decimal places) 
    score for each content object, and allows voting only for authenticated
    users.
    
    The default rating handler uses the project's settings as options: this 
    way you can register not customized rating handlers and then modify
    their options just editing the settings file.
    
    Most common rating needs can be handled by subclassing *RatingHandler* 
    and changing the values of pre-defined attributes; 
    the full range of built-in options is as follows.
    
    
    **allow_anonymous**: set to False to allow votes only by authenticated 
    users (default: *False*)
    
    **score_range**: must be a tuple of min and max values for scores,
    including the extremes (default: *(1, 5)*)
    
    **vote_decimals**: how many decimal places are allowed in scores
    (default: *0*)
    
    **default_key**: default key to use for votes when there is only one 
    vote-pre-content (default: *'main'*)
    
    **can_delete_vote**: set to False if you do not want to allow users to
    delete a previously saved vote (default: *True*)
    
    **can_change_vote**: set to False if you do not want to allow users to
    change the score of a previously saved vote (default: *True*)
    
    **next_querystring_key**: querystring key that can contain the url of 
    the redirection performed after voting (default: *'next'*)
    
        
    For situations where the built-in options listed above are not sufficient, 
    subclasses of *RatingHandler* can also override the methods which 
    actually perform the voting process, and apply any logic they desire.
    """
    allow_anonymous = settings.ALLOW_ANONYMOUS
    score_range = settings.SCORE_RANGE
    vote_decimals = settings.VOTE_DECIMALS
    default_key = settings.DEFAULT_KEY
    next_querystring_key = settings.NEXT_QUERYSTRING_KEY
    can_delete_vote = True
    can_change_vote = True
    
    def __init__(self, model):
        self.model = model
            
    def get_key(self, request, instance):
        """
        Return the ratings key to be used to save the vote.

        Subclasses of this handler can define multiple keys to be used
        depending on given *request* or, more probably, on the given
        *instance* (the target object being voted).
        """
        return default_key
        
    # voting
        
    def get_vote_form_class(self, request):
        """
        Return the vote form class that will be used to handle voting.
        
        This method can be overridden by view-level passed form class.
        """
        return forms.VoteForm
        
    def get_vote_form_kwargs(self, request):
        """
        Return the optional kwargs used to instantiate the voting form.
        """
        return {'score_range': self.score_range}
            
    def allow_vote(self, request, vote):
        """
        Called just before the vote is saved to the db, this method takes
        the *request* and the unsaved *vote* instance.
        
        The unsaved vote can be a brand new vote instance (without *id*)
        or an existing vote object the user want to change.
        
        Subclasses can use this method to check if the vote can be saved and,
        if necessary, block the voting process returning False.
        
        This method is called by a *signals.vote_will_be_saved* listener
        always attached to the handler.
        It's up to the developer if override this method or just connect
        another listener to the signal: the voting process is killed if 
        just one receiver returns False.
        """
        return self.can_change_vote if vote.id else True
        
    def vote(self, request, vote):
        """
        Save the vote to the database.
        Must return True if the *vote* was created, False otherwise.
        
        By default this method just does *vote.save()* and recalculates
        the related score (average, total, number of votes).
        """
        created = not vote.id
        vote.save()
        models.upsert_score(vote.content_object, vote.key)
        return created
        
    def post_vote(self, request, vote, created):
        """
        Called just after the vote is saved to the db.
        
        This method is called by a *signals.vote_was_saved* listener
        always attached to the handler.
        """
        pass
        
    # deleting vote
    
    def allow_delete(self, request, vote):
        """
        Called just before the vote is deleted from the db, this method takes
        the *request* and the *vote* instance.
        
        Subclasses can use this method to check if the vote can be deleted and,
        if necessary, block the vote deletion process returning False.
        
        This method is called by a *signals.vote_will_be_deleted* listener
        always attached to the handler.
        It's up to the developer if override this method or just connect
        another listener to the signal: the voting deletion process is killed 
        if just one receiver returns False.
        """
        return self.can_delete_vote and vote.id
        
    def delete(self, request, vote):
        """
        Delete the vote from the database.
        
        By default this method just do *vote.delete()* and recalculates
        the related score (average, total, number of votes).
        """
        vote.delete()
        models.upsert_score(vote.content_object, vote.key)
        
    def post_delete(self, request, vote):
        """
        Called just after the vote is deleted to from db.
        
        This method is called by a *signals.vote_was_deleted* listener
        always attached to the handler.
        """
        pass
        
    # view callback
    
    def success_response(self, request, vote):
        """
        Callback used by the voting views, called when the user successfully
        voted. Must return a Django http response (usually a redirect).
        """
        from django.shortcuts import redirect
        next = request.REQUEST.get('next')
        return redirect
        
    def failure_response(self, request):
        """
        Callback used by the voting views, called when vote form did not 
        validate. Must return a Django http response.
        """
        from django.http import HttpResponseBadRequest
        return HttpResponseBadRequest('Invalid data in vote form.')
    
    # utils
            
    def has_voted(self, request, instance, key):
        """
        Return True if the user related to given *request* has voted the
        given target object *instance* using the given *key*.
        """
        pass
        
    def get_vote(self, request, instance, key):
        """
        Return the vote instance created by the user related to *request*
        for the target object *instance* usingthe given *key*.
        
        Return None if the vote does not exists.
        """
        pass
                
    def score_for(self, instance, key):
        """
        Return the score for the target object *instance* and the given *key*. 
        """
        pass
            
     
class Ratings(object):
    """
    Registry that stores the handlers for each content type rating system.

    An instance of this class will maintain a list of one or more models 
    registered for being rated, and their associated handler classes.

    To register a model, obtain an instance of *Ratings* (this module exports 
    one as *ratings*), and call its *register* method, passing the model class 
    and a handler class (which should be a subclass of *RatingHandler*). 
    Note that both of these should be the actual classes, not instances 
    of the classes.

    To cease ratings handling for a model, call the *unregister* method,
    passing the model class.

    For convenience, both *register* and *unregister* can also accept a list 
    of model classes in place of a single model; this allows easier 
    registration of multiple models with the same *RatingHandler* class.
    """
    def __init__(self):
        self._registry = {}
        self.connect()

    def connect(self):
        """
        Pre and post (delete) vote signals.
        """
        signals.vote_will_be_saved.connect(self.pre_vote, sender=models.Vote)
        signals.vote_was_saved.connect(self.post_vote, sender=models.Vote)
        signals.vote_will_be_deleted.connect(self.pre_delete, sender=models.Vote)
        signals.vote_was_deleted.connect(self.post_delete, sender=models.Vote)

    def register(self, model_or_iterable, handler_class):
        """
        Register a model or a list of models for ratings handling, using a 
        particular *handler_class*.

        Raise *AlreadyHandled* if any of the models are already registered.
        """
        if isinstance(model_or_iterable, ModelBase):
            model_or_iterable = [model_or_iterable]
        for model in model_or_iterable:
            if model in self._registry:
                raise exceptions.AlreadyHandled(
                    "The model '%s' is already being handled" % 
                    model._meta.module_name)
            self._registry[model] = handler_class(model)

    def unregister(self, model_or_iterable):
        """
        Remove a model or a list of models from the list of models that will
        be handled.

        Raise *NotHandled* if any of the models are not currently registered.
        """
        if isinstance(model_or_iterable, ModelBase):
            model_or_iterable = [model_or_iterable]
        for model in model_or_iterable:
            if model not in self._registry:
                raise exceptions.NotHandled(
                    "The model '%s' is not currently being handled" % 
                    model._meta.module_name)
            del self._registry[model]
            
    def get_handler(self, model):
        """
        Return the handler for *model* 
        Return None if model is unregistered.
        """
        return self._registry[model] if model in self._registry else None

    def pre_vote(self, sender, vote, request, **kwargs):
        """
        Apply any necessary pre-save ratings steps to new votes.
        """
        model = vote.content_type.model_class()
        if model not in self._registry:
            return False
        return self._registry[model].allow_vote(request, vote)

    def post_vote(self, sender, vote, request, created, **kwargs):
        """
        Apply any necessary post-save ratings steps to new votes.
        """
        model = vote.content_type.model_class()
        if model not in self._registry:
            return
        return self._registry[model].post_vote(request, vote, created)
        
    def pre_delete(self, sender, vote, request, **kwargs):
        """
        Apply any necessary pre-delete ratings steps.
        """
        model = vote.content_type.model_class()
        if model not in self._registry:
            return False
        return self._registry[model].allow_delete(request, vote)

    def post_delete(self, sender, vote, request, **kwargs):
        """
        Apply any necessary post-delete ratings steps.
        """
        model = vote.content_type.model_class()
        if model not in self._registry:
            return
        return self._registry[model].post_delete(request, vote)


# import this instance in your code to use in registering models for ratings
ratings = Ratings()
