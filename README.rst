
Lotse
===================

A framework for developing strategy-based guidance components for visual analytics components.

The aim of this library is to facilitate integrating strategy-based guidance into visual analytics applications with minimal programming or engineering effort necessary. The framework has been designed to cover the state of the art in guidance research. Its core features are:

1. **Guidance specification:** Lotse allows users to define one or multiple guidance strategies in the form of yaml files. The files contain a mixture of declarative specification and python snippets, where necesary.

2. **Rich, well-specified interaction model:** Lotse provides clear interfaces for communication between the visualization components and the guidance engine. New suggestions are streamed over a websocket to enable true mixed-initiative interactions. User interactions with guidance, as well as changes in the analysis context can be sent to the guidance engine via well-documented REST interaces.

3. **Auto-configuration:** To adapt the provided guidance, simply add new strategies and actions. All yaml files are parsed automatically with no need for tedious manual adjustments in several files.


Installation
------------

FastAPI-Integration
  If you already have a running FastAPI application, you can integrate Lotse as sub-application within two lines of code. For a full example, see https://github.com/lotse-guidance/demonstrator.

  1. Add Lotse to your requirements.txt: `lotse==1.0.0`
  2. Import Lotse and mount it:

        from guidance_strategies.app.main import app as guidance_engine

        app.mount('/your-path', guidance_engine)

Standalone
  Lotse brings its own FastAPI instance, allowing it to run standalone. In this case, some configuration is necessary to corectly load strategy- and action-templates. Again, see https://github.com/lotse-guidance/demonstrator for an example.

We are working on providing alternative ways of integrating Lotse that do not rely on FastAPI.

Documentation
-------------

Assuming you started Lotse at `http:localhost:8019`, interactive documentation is available at `http://localhost:8019/your-path/docs`.

Usage
-----

Define Strategies, Action and analysis states
*********************************************

Lotse, is centered around the concept of strategies that provide actions which should be suggested in given analysis contexts. Which actions or strategies are executed in which contexts is initially defined by rules and conditions specified in the respective yaml files, and can easily be updated throughout the guidance session.

Analysis State Definition
+++++++++++++++++++++++++

The analysis state definition will be used to decide when to deploy which strategies and actions. It is defined in a yaml file like so. The available yaml syntax is summarized below.::

    # load JSON from REST endpoint
    #data:
    #  url: "https://your.server/data.json"
    #  type: api_json

    # load data from local CSV file
    data:
      file_path: "../data/measurements.csv"
      type: from_csv

    # initialize analysis state
    last_interaction: 0
    month: "2015-01-31"
    x_axis: humidity
    y_axis: pressure


    # custom helper function
    get_current_month:
      type: function # specify type:function to define functions
      args: [] # define the list of expected arguments
      # define the callback in python syntax
      load: |
          return list(filter(lambda p: p['date'] == self.month, self.data))


    # INITIALIZE
    initialize:
      args: []
      import: [time] # you can also import python modules you might need in your callbacks
      load: self.last_interaction = int(time.time())

    # CALLBACKS

    # a custom callback to store in which dimensions a datapoint was hovered
    update_hover:
      type: function
      args: [station, dim1, dim2] # arguments to be specified via the REST endpoint
      load: |
          dp = next(dp for dp in self.get_current_month() if dp['station'] == station)
          dp['hovered'] = [dim1, dim2]
          return dp


Initialize Callback
^^^^^^^^^^^^^^^^^^^

This callback, if implemented, is automatically called by Lotse when instantiating the analysis state for the first time. It allows custom initialization logic to be executed, e.g. for initializing time variables as shown in the example, or loading data from a file.

Note that this method is called on the analysis state object itself, so any properties needed can be accessed via `self.property_name`.

The analysis state can be manipulated using two methods:

GuidanceEngine::update_state
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

`update_state()` allows simple updates of the state vector by specifying key-value pairs to be updated. For more complex update logic, see `update_state_with_callback()`.

:updates: A dictionary of key-value pairs to be updated in the state vector
:re_evaluate_strategies: Whether to immediately re-evaluate the applicability of all strategies after the analysis state update (True) or not (False). Defaults to False.
:re_evaluate_actions: Whether to immediately re-evaluate all actions of active strategies after the analysis state update (True) or not (False). Defaults to True.

GuidanceEngine::update_state_with_callback
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

`update_state_with_callback()` allows complex updates of the state vector by specifying a callback from the analysis state yaml to be called with the specified arguments.

:callback: The name of the callback to execute, as specified in the analysis state yaml.
:params: A dictionary of parameter-names and -values to pass to the callback. Parameter names must match the names specified in the analysis state yaml, positional arguments to the callback are currently not supported.
:re_evaluate_strategies: Whether to immediately re-evaluate the applicability of all strategies after the analysis state update (True) or not (False). Defaults to False.
:re_evaluate_actions: Whether to immediately re-evaluate all actions of active strategies after the analysis state update (True) or not (False). Defaults to True.

Guidance Strategies
+++++++++++++++++++

Once your state vector is defined, you can define guidance strategies: ::

    # Metadata object. You must specify a name, ID and the intended degree. Arbitrary additional fields are possible
    # but not required.
    metadata:
      strategy: Timeslider
      description: Suggests an alternative month to investigate
      strategy_id: month_change
      degree: orienting

    # Each strategy must contain one action, to be loaded from a file specified under `file_path`.
    action:
      file_path: actions/slider_action.yaml

    # Each strategy must implmement the method `determine_applicability` which is used to decide which strategies should
    # be activated or deactivated in which scenarios.
    determine_applicability:
      args: [ctx, delta]
      load: |
        return True

Strategy::determine_applicability
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To determine which strategies are currently active and should potentially generate suggestions, Lotse calls the `determine_applicability()`-method. Calls automatically happen periodically on a pre-defined tick timer, or if requested when updating the state vector.

:state: The current analysis analysis state.
:delta: The analysis state change introduced in the last state update
:returns: True or False, depending on whether the strategy is applicable or not.

Guidance Action
+++++++++++++++

The guidance action is responsible for generating suggestion content, handling acceptance and rejection, including updates to the rules in which it should be deployed. An action's strategy is always available via `action.strategy`. ::

    # Must be specified
    type: action

    # degree and action_id are mandatory metadata parameters.
    metadata:
      description: Suggests an alternative month to investigate
      degree: orienting

    # Arbitrary field defined to hold a threshold value.
    timeout: 10

    # This methods must be implemented as it is frequently called by the framework.
    is_applicable:
      args: [ctx, delta]
      import: [time]
      load: |
        # overly simplistic for the sake of this example
        return int(time.time()) - ctx.last_interaction > self.timeout and not self.suggested

    # This method is called by the framework whenever the action is determined to be applicable in the current context.
    generate_suggestion_content:
      args: [ctx]
      import: [datetime, calendar]
      load: |
          # arbitrary python logic
          d = datetime.datetime.strptime(ctx.month, '%Y-%m-%d').date()
          suggestion = datetime.date(d.year, d.month + 1, calendar.monthrange(d.year, d.month + 1)[-1])

          return (suggestion, 'Move', 'Consider moving to the next month!')

    # Called by the framework whenever the suggestion is accepted
    accept:
      load: |
        self.timeout *= .95
        self.suggested = False

    # Called by the framework whenever the suggestion is rejected.
    reject:
      load: |
        self.timeout += 10
        self.suggested = False

    # Optionally, you define two additional callbacks `preview_start(ctx)` and `preview_end(ctx)` that will be called by
    # the framework at appropriate times.



GuidanceAction::is_applicable
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To determine which actions (from the active strategies) are currently active and should generate suggestions, Lotse calls the `is_applicable()`-method. Calls automatically happen periodically on a pre-defined tick timer, or if requested when updating the state vector.

:state: The current analysis analysis state.
:delta: The analysis state change introduced in the last state update.
:returns: True or False, depending on whether the action is applicable or not.

GuidanceAction::generate_suggestion_content
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This method is called by Lotse whenever the action is applicable.

:state: The current analysis state.
:returns: (Content, title, description): A tuple containing the suggestion content, a title for the suggestion and a justifying or explaining description. Both title and description are intended to be shown to the user to make the guidance process more transparent. The suggestion content can be any arbitrary data structure, as long as it can be JSON-serialized.

GuidanceAction::accept
^^^^^^^^^^^^^^^^^^^^^^

Guidance actions can be accepted by sending an appropriate REST request (see `localhost:8019/guidance/docs` after starting Lotse).

Whenever an action is accepted, its accept method is called and can, for example, modify the rules and criteria used to determine whether the action itself or its strategy is applicable.

:suggestion: The suggestion that was accepted.
:state: The analysis state in which the suggestion was accepted.
:delta: The analysis state change introduced in the last state update.

GuidanceAction::reject
^^^^^^^^^^^^^^^^^^^^^^

Guidance actions can be rejected by sending an appropriate REST request (see `localhost:8019/guidance/docs` after starting Lotse).

Whenever an action is rejected, its reject method is called and can, for example, modify the rules and criteria used to determine whether the action itself or its strategy is applicable.

:suggestion: The suggestion that was rejected.
:state: The analysis state in which the suggestion was accepted.
:delta: The analysis state change introduced in the last state update.


Retracting Suggestions
++++++++++++++++++++++

Over time, it is likely that previously made suggestions will become outdated and need to be retracted. To that end, each action can implement a `should_retract` and `retract` callback.
While the first determines whether a retraction is possible and sends an appropriate socket message if so, the second can be used to cleanup the analysis state or make other necessary adjustments.

GuidanceAction::should_rectract
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In every tick of the guidance loop, Lotse verifies for all current suggestions whether they need to be retracted by calling the `should_rectract` callback of their respective actions.

:suggestion: The suggestion that should be tested for retraction
:state: The current analysis state
:delta: The analysis state change introduced in the last state update.

If the callback returns `True`, an appropriate retraction message is sent via the websocket automatically.

GuidanceAction::retract
^^^^^^^^^^^^^^^^^^^^^^^

If the `should_rectract` callback returned true and the suggestion was retracted, this callback is called and can be used, for example,  to clean up the state

:suggestion: The suggestion that was rejected.
:state: The analysis state in which the suggestion was accepted.
:delta: The analysis state change introduced in the last state update.


Meta Strategy
+++++++++++++

When you implement several strategies, it might happen that multiple strategies aim  to provide new suggestions in a given state.
Whether this is desired or not is highly dependent on your setup and your guidance needs.

To orchestrate which actions actually produce suggestions, you can implement a meta strategy in the guidance orchestrator: ::

    metadata:
      strategy: Meta Strategy
      description: Always prioritize outliers over time slider, if possible.

    filter_actions:
      args: [actions, ctx]
      load: |
        return sorted(actions, key=lambda a: a.metadata['priority'])[-1:]

The corresponding yaml file mussed be placed with all other strategies and be called `meta.yaml`.


MetaStrategy::filter_actions
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In each iteration of the guidance loop, the `filter_actions` callback--if defined--is passed the list of actions that are applicable in the current context.
It must then return an array of actions that should be allowed to produce suggestions.

:actions: All actions that are applicable in the given state
:state: The analysis state in which the suggestion was accepted.

Providing Guidance
******************


Guidance Engine Flow
++++++++++++++++++++
As mentioned above, Lotse runs two internal tick timers that can be configured (see "Custom Guidance- and Inference Loop Timers")

1. The strategy timer runs every 30 seconds and determines which strategies are currently applicable.
2. The action timer runs every 2 seconds and determines which actions from the active strategies are currently applicable.

The flow through the framework is then as follows:

1. Determine applicable strategies
2. Determine applicable actions
3. Retract obsolete suggestions
4. Filter applicable actions using meta strategy
5. Generate new suggestions: Call `generate_suggestion_content()` methods, obtaining a suggestion including title and description.
6. Add some suggestion-metadata (`strategy_id`, `action_id`, ...) and JSON-serialize the suggestion
7. Send the suggestion via the websocket

The loop always restarts at (2), which will return different results if strategies have been enabled or disabled in the meantime.


Client-Server Interaction
+++++++++++++++++++++++++

To enable mixed-initiative guidance interactions, Lotse relies on both REST interfaces and a websocket connection. The websocket allows Lotse to send new suggestions as soon as they have been generated, without having to wait for clients to poll for new suggesions.

However, websocket communication is harder to debug and document than REST interfaces. Consequently, Lotse uses REST interfaces for all communication from the client back to the guidance engine.

The interactive documentation of all REST endpoints is available at `localhost:8019/guidance/docs`.

Websocket: Streaming new Suggestions
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

New suggestions are streamed via the websocket as soon as they are generated. If multiple actions produce suggesions in a single tick timer evaluation, all suggestions are sent sequentially, in individual socket messages.

Suggestions follow this schema: ::

    {
      type: 'guidance',
      interaction: 'make'
      suggestion: {
        id: str,
        strategy: str,
        title: str,
        description: str,
        degree: str
        event: {
          value: Any,
          action_id: str
        }
      }
    }

The `id` is an automatically generated uuid. `strategy`, `action_id`, and `degree` are automatically filled from the strategy and action that produced this suggestion. `value`, `title`, and `description` are fields of the tuple returned by `generate_suggestion_content()`.

`action_id` and `strategy` are included with each suggestion to enable visualization components to apply filters and only react to certain guidance suggestions. For example, a suggestion to highlight specific data points might be relevant for a scatter plot, but not for a date selection component.

REST Endpoints: Accepting and rejecting guidance
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To accept or reject guidance suggestions, call the respective endpoints `/guidance/accept` or `/guidance/reject`. The payload should be the suggestion to be accepted/rejected. Within the payload, the `interaction` should be replaced with `accept` or `reject` accordingly.::

    {
      type: 'guidance',
      interaction: 'accept'
      suggestion: {
        id: str,
        strategy: str,
        title: str,
        description: str,
        degree: str
        event: {
          value: Any,
          action_id: str
        }
      }
    }

Advanced Usage
--------------
Custom Guidance- and Inference Loop Timers
******************************************

By default, Lotse calls the guidance loop every two seconds and the inference loop every 30 seconds.
You can override both values when setting up your engine using the `setup_engine()`-Method.

Custom State Vector Initialization
**********************************

In some cases the `initialize()`-method defined in the analysis state yaml might not be sufficient to setup the state vector, for example when database access is needed and credentials need to be passed in. In such cases, developers can fall back to implementing some python code: ::

    from guidance_strategies.app.main import app as guidance_engine
    data = [] # get data from somewhere, e.g. connect to database etc.
    guidance_engine.update_state('data', data)

Starting and Stopping the Engine
********************************

Similar to the `update_state()` method introduced above, the guidance engine also provides `start()` and `stop()` methods that can be called from python when needed.

Additionally, Lotse exposes two REST interfaces `/guidance/start` and `/guidance/stop` that can be called from the frontend to control the guidance engine's state.


Advanced Suggestion Interactions
********************************

In some scenarios it might be necessary to know when users start and end previewing the provided guidance suggestions, assuming that the interface affords such interactions.

GuidanceAction: preview_start
+++++++++++++++++++++++++++++

To register the start of a guidance preview, call `/guidance/preview_start` with the suggestion, similar to calling the endpoints for accepting or rejecting suggestions. Lotse will then automatically call the `preview_start()` method defined in the action that generated the suggestion.

:suggestion: The suggestion for which a preview was started.
:state: The analysis state in which the preview started
:delta: The analysis state change introduced in the last state update.

GuidanceAction:preview_end
++++++++++++++++++++++++++
To register the end of a guidance preview, call `/guidance/preview_end` with the suggestion, similar to calling the endpoints for accepting or rejecting suggestions. Lotse will then automatically call the `preview_end()` method defined in the action that generated the suggestion.

:suggestion: The suggestion for which a preview was started.
:state: The analysis state in which the preview ended
:delta: The analysis state change introduced in the last state update.

Strategies and Actions: Arbitrary fields and functions
******************************************************

When defining strategies and actions, designers must specify the few functions outlined above. In addition, they can add arbitrary fields or functions using the syntax described below.
As the examples above show this is, for example, useful to define thresholds or rulesets for determining when strategies and actions should be applicable.

You can use common yaml syntax to define maps, lists, etc.

If you want to define custom callbacks beyond those that Lotse offers already, consider the following example: ::

    # helper function to return only data from the current month
    get_current_month:
      type: function # specify type:function to define callback functions
      args: [] # define the list of expected arguments
      import: [] # optional array of python modules to import
      # define the callback in python syntax
      load: |
          return list(filter(lambda p: p['date'] == self.month, self.data))

Licence
-------

Apache 2.0 Licence.

Authors
-------

`Lotse` was written by `Fabian Sperrle <fabian.sperrle@uni-konstanz.de>`_ and conceptualized by Fabian Sperrle, Davide Ceneda, and Mennatallah El-Assady.
