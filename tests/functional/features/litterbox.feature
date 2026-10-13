Feature: Controlling the litterbox from the command line
  An owner runs petsnowy against their Snow+ litterbox on the home network.

  Background:
    Given a reachable litterbox in standby

  Scenario: Starting a manual clean
    When I run "petsnowy clean"
    Then the command succeeds with "Clean cycle triggered."
    And the litterbox reports status "cleaning"

  Scenario: Locking the buttons uses the inverted lock data point
    When I run "petsnowy child-lock on"
    Then the command succeeds with "Child lock set to True."
    And data point 104 was written as false
    And the litterbox reports its buttons locked

  Scenario: Seeing that the cat is in the box
    Given the cat has stepped into the litterbox
    When I run "petsnowy status"
    Then the command succeeds with "Cat present:        YES"

  Scenario Outline: Bad input is refused before anything is sent
    When I run "<command>"
    Then the command fails with exit code 2 mentioning "<message>"
    And nothing was written to the litterbox

    Examples:
      | command                   | message                 |
      | petsnowy light dim        | expected on/off         |
      | petsnowy clean-delay soon | expected a whole number |
      | petsnowy sleep            | sleep on\|off           |
      | petsnowy hover            | Unknown litterbox       |
